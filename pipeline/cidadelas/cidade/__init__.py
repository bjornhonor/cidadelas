"""Uma cidade por dentro: os indicadores do ranking calculados por zona (ver zonas.py), para comparar as zonas.

    python -m cidadelas cidade valinhos

Config em config/cidades/<cidade>.yaml. Depende de `coletar ssp_bo`, `coletar censo_setores`, `coletar rotas` e
`coletar mapbiomas`. Grava web/public/data/cidades/<cidade>.json e <cidade>.geojson, no mesmo formato do estado.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from ..calculo import saude
from ..calculo.natureza import VERDE, percentual_no_raio
from ..exportar import DESTINO as DESTINO_ESTADO
from ..nomes import chave_nome
from ..paths import RAIZ
from .zonas import zonas

DESTINO = DESTINO_ESTADO / "cidades"
# Destinos além disso não entram: a curva de emergência zera em 90 min, e o raio da capacidade é de 30 min
RAIO_ACESSO_KM = 150
RAIO_CAPACIDADE_KM = 60  # 30 min de rodovia livre
TEMPO_ACESSO = timedelta(minutes=90)
PREFIXOS_BAIRRO = ("bairro", "jardim", "vila", "parque", "residencial", "chacaras", "chacara", "sitios", "loteamento")


def _chave_bairro(nome: str) -> str:
    """Casa "BAIRRO PINHEIRO" do BO com "Pinheiro" do OSM, e "JD. SANTA ROSA" com "Jardim Santa Rosa"."""
    chave = chave_nome(nome.replace("JD.", "JARDIM ").replace("Jd.", "Jardim "))
    for p in PREFIXOS_BAIRRO:
        if chave.startswith(p) and len(chave) > len(p) + 2:
            return chave[len(p):]
    return chave


def _seguranca(con, s: gpd.GeoDataFrame, bairros: gpd.GeoDataFrame, cod_ibge: int) -> pd.DataFrame:
    """Crime por zona: coordenada do BO quando existe; senão, o bairro do BO.

    Crime em residência vem sem coordenada (a SSP omite), mas com bairro. Cada nome de bairro vai para a zona onde
    caem a maioria dos BOs com coordenada daquele bairro; nome que nunca aparece com coordenada vai pelo ponto do
    bairro no OpenStreetMap. "Zona rural" vai para a zona com mais moradores em setor rural.
    """
    bo = con.execute("SELECT * FROM ssp_bo WHERE cod_ibge = ?", [cod_ibge]).df()
    anos = con.execute("SELECT count(DISTINCT ano) FROM ssp_bo").fetchone()[0]
    pontos = gpd.GeoDataFrame(bo, geometry=gpd.points_from_xy(bo["lon"], bo["lat"]), crs=4326).to_crs(s.crs)
    bo["zona"] = gpd.sjoin(pontos, s[["zona", "geometry"]], how="left", predicate="within")["zona"].groupby(level=0).first()
    bo["chave"] = bo["bairro"].map(lambda b: _chave_bairro(b) if isinstance(b, str) else None)

    votos = bo.dropna(subset=["zona", "chave"]).groupby(["chave", "zona"]).size().reset_index(name="n")
    por_bairro = votos.sort_values("n").drop_duplicates("chave", keep="last").set_index("chave")["zona"].to_dict()
    for chave, zona in zip(bairros["nome"].map(_chave_bairro), bairros["zona"]):
        por_bairro.setdefault(chave, zona)
    rural = s[s["situacao"] == "8"].groupby("zona")["pop"].sum()
    if len(rural):
        por_bairro.setdefault("zonarural", rural.idxmax())
    # O campo do BO às vezes vem cortado ("BAIRRO ESPIRITO SANT"): vale se for o começo de um só bairro conhecido
    for chave in set(bo["chave"].dropna()) - set(por_bairro):
        candidatos = {z for k, z in por_bairro.items() if len(chave) >= 8 and k.startswith(chave)}
        if len(candidatos) == 1:
            por_bairro[chave] = candidatos.pop()

    origem = np.where(bo["zona"].notna(), "coordenada", np.where(bo["chave"].map(por_bairro).notna(), "bairro", "sem zona"))
    bo["zona"] = bo["zona"].fillna(bo["chave"].map(por_bairro))
    resumo = pd.crosstab(bo["indicador"], origem, normalize="index").round(2)
    print(f"  crimes por zona, de onde veio a zona:\n{resumo.to_string()}")
    sem_zona = bo[bo["zona"].isna()]
    if len(sem_zona):
        print(f"  sem zona ({len(sem_zona)}): {sem_zona['bairro'].value_counts().head(8).to_dict()}")

    pop = s.groupby("zona")["pop"].sum()
    linhas = []
    for indicador, g in bo.dropna(subset=["zona"]).astype({"zona": int}).groupby("indicador"):
        eventos = g.groupby("zona").size().reindex(pop.index, fill_value=0)
        linhas.append(pd.DataFrame({
            "zona": pop.index, "indicador": indicador, "eventos": eventos.to_numpy(),
            "valor": (eventos / (pop * anos) * 100_000).to_numpy(), "unidade": "por 100 mil hab/ano",
        }))
    return pd.concat(linhas).assign(topico="seguranca", anos=anos)


def _rotear(con, s: gpd.GeoDataFrame, buscas: list[tuple[pd.DataFrame, timedelta, str]], slug: str, forcar: bool) -> pd.DataFrame:
    """Tempo de carro de cada setor habitado até as unidades de saúde da região (cache no banco).

    buscas: (destinos, tempo máximo, rótulo). Como em fontes/rotas.py, a busca longa vai só até hospitais e PS: o
    custo cresce muito com o tempo máximo.
    """
    tabela = f"cidade_{slug}_tempos"
    if not forcar and con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [tabela]).fetchone()[0]:
        print(f"  rotas: cache em {tabela}")
        return con.execute(f"SELECT * FROM {tabela}").df()
    import r5py  # sobe uma JVM: só quando precisa rotear

    from ..download import baixar
    from ..fontes.rotas import ORIGENS_POR_LOTE, THREADS, URL_OSM

    origens = s[s["pop"] > 0].to_crs(4326)
    origens = gpd.GeoDataFrame({"id": origens["cd_setor"]}, geometry=origens.geometry.representative_point(), crs=4326)
    rede = r5py.TransportNetwork(baixar("osm", "sao-paulo-latest.osm.pbf", URL_OSM))
    lotes = [origens.iloc[i:i + ORIGENS_POR_LOTE] for i in range(0, len(origens), ORIGENS_POR_LOTE)]
    partes = []
    for destinos, tempo_maximo, rotulo in buscas:
        alvo = gpd.GeoDataFrame({"id": destinos["id"]}, geometry=gpd.points_from_xy(destinos["lon"], destinos["lat"]), crs=4326)
        feitos = 0

        def rotear(lote):
            nonlocal feitos
            m = r5py.TravelTimeMatrix(
                rede, origins=lote, destinations=alvo, transport_modes=[r5py.TransportMode.CAR],
                departure=datetime(2026, 9, 1, 10, 0), max_time=tempo_maximo,  # o horário só importa para ônibus
            )
            feitos += len(lote)
            print(f"    {rotulo}: {feitos}/{len(origens)} setores", flush=True)
            return pd.DataFrame(m).dropna(subset=["travel_time"])

        print(f"  rotas ({rotulo}): {len(origens)} setores x {len(alvo)} destinos, até {tempo_maximo}", flush=True)
        with ThreadPoolExecutor(THREADS) as executor:
            partes.extend(executor.map(rotear, lotes))
    tempos = (
        pd.concat(partes, ignore_index=True)
        .rename(columns={"from_id": "origem", "to_id": "destino", "travel_time": "minutos"})
        .groupby(["origem", "destino"], as_index=False)["minutos"].min()
    )
    con.execute(f"CREATE OR REPLACE TABLE {tabela} AS SELECT * FROM tempos")
    return tempos


def _saude(con, cfg_estado: dict, cfg: dict, s: gpd.GeoDataFrame, slug: str, forcar: bool) -> pd.DataFrame:
    """Mesmo cálculo do estado, com cada setor como origem.

    A disputa por cada leito ou médico (quantas pessoas alcançam a unidade) vem do cálculo do estado, que considera
    a população de toda a região; aqui só muda de onde se parte.
    """
    raio = cfg["topicos"]["saude"]["raio_capacidade_min"]
    acessos, capacidades = saude.conjuntos(con, cfg_estado)
    destinos = con.execute("SELECT co_unidade, celula, lat, lon FROM rotas_destinos").df()
    centro = s.to_crs(4326).union_all().centroid
    km = np.hypot((destinos["lat"] - centro.y) * 111, (destinos["lon"] - centro.x) * 111 * np.cos(np.radians(centro.y)))
    unidades_acesso = set().union(*acessos.values())
    com_oferta = set().union(*(oferta.index for oferta, _, _ in capacidades.values()))
    acesso = destinos[(km <= RAIO_ACESSO_KM) & destinos["co_unidade"].isin(unidades_acesso)]
    celulas = destinos[(km <= RAIO_CAPACIDADE_KM) & destinos["celula"].isin(com_oferta)]
    tempos = _rotear(con, s, [
        (acesso.rename(columns={"co_unidade": "id"})[["id", "lat", "lon"]], TEMPO_ACESSO, "acesso"),
        (celulas.groupby("celula", as_index=False)[["lat", "lon"]].mean().rename(columns={"celula": "id"}),
         timedelta(minutes=raio), "capacidade"),
    ], slug, forcar)

    origens_estado = con.execute("SELECT * FROM rotas_origens").df()
    tempos_estado = con.execute("SELECT * FROM rotas_tempos").df()
    pop = s.set_index("cd_setor")["pop"]

    def por_zona(valor_setor: pd.Series) -> pd.Series:
        v = s[s["pop"] > 0][["cd_setor", "zona", "pop"]].assign(v=lambda d: d["cd_setor"].map(valor_setor).to_numpy())
        return v.groupby("zona").apply(lambda g: np.average(g["v"], weights=g["pop"]), include_groups=False)

    linhas = []
    for indicador, conjunto in acessos.items():
        t = tempos[tempos["destino"].isin(conjunto)].groupby("origem")["minutos"].min().reindex(pop.index)
        nota = pd.Series(np.interp(t.fillna(999), *saude.CURVA_EMERGENCIA), index=t.index)
        minutos = por_zona(t.fillna(saude.CURVA_EMERGENCIA[0][-1]))
        n = por_zona(nota)
        linhas.append(pd.DataFrame({"zona": n.index, "indicador": indicador, "valor": n.to_numpy(),
                                    "minutos": minutos.to_numpy(), "unidade": "nota de acesso (0 a 100)"}))
    for indicador, (oferta, por, unidade) in capacidades.items():
        razao = saude.razao_oferta(origens_estado, tempos_estado, oferta, raio)
        v = por_zona(saude.acessivel(tempos, razao, raio).reindex(pop.index).fillna(0)) * por
        linhas.append(pd.DataFrame({"zona": v.index, "indicador": indicador, "valor": v.to_numpy(), "unidade": unidade}))
    return pd.concat(linhas).assign(topico="saude")


def _infraestrutura(con, s: gpd.GeoDataFrame) -> pd.DataFrame:
    san = con.execute("SELECT * FROM censo_setor_saneamento WHERE cd_setor IN (SELECT unnest(?))", [list(s["cd_setor"])]).df()
    z = san.merge(s[["cd_setor", "zona"]], on="cd_setor").groupby("zona")[["domicilios", "agua_rede", "esgoto_rede"]].sum()
    valor = 100 * (z["agua_rede"] + z["esgoto_rede"]) / (2 * z["domicilios"])
    return pd.DataFrame({
        "zona": valor.index, "indicador": "saneamento", "valor": valor.to_numpy(), "topico": "infraestrutura",
        "unidade": "% médio de domicílios com água e com esgoto na rede geral (Censo 2022)",
    })


def _natureza(cfg: dict, s: gpd.GeoDataFrame) -> pd.DataFrame:
    n = cfg["topicos"]["natureza"]
    medidas = {
        "verde_perto": (VERDE, n["raio_perto_km"]),
        "verde_regiao": (VERDE, n["raio_regiao_km"]),
        "area_urbana": (["urbana"], n["raio_perto_km"]),
    }
    habitados = s[s["pop"] > 0]
    ponto = habitados.to_crs(4326).geometry.representative_point()
    por_setor = pd.DataFrame({"zona": habitados["zona"].to_numpy(), "pop": habitados["pop"].to_numpy(),
                              **percentual_no_raio(ponto.x.to_numpy(), ponto.y.to_numpy(), medidas)})
    unidades = {
        "verde_perto": f"% de mata, campo ou sítio a até {n['raio_perto_km']} km de casa (média dos moradores)",
        "verde_regiao": f"% de mata, campo ou sítio a até {n['raio_regiao_km']} km de casa (média dos moradores)",
        "area_urbana": f"% de área urbanizada a até {n['raio_perto_km']} km de casa (média dos moradores)",
    }
    media = por_setor.groupby("zona").apply(
        lambda g: pd.Series({i: np.average(g[i], weights=g["pop"]) for i in medidas}), include_groups=False,
    )
    return (
        media.reset_index().melt(id_vars="zona", var_name="indicador", value_name="valor")
        .assign(topico="natureza", unidade=lambda d: d["indicador"].map(unidades))
    )


def calcular(con: duckdb.DuckDBPyConnection, cfg_estado: dict, slug: str, rotear_de_novo: bool = False) -> None:
    cfg = yaml.safe_load((RAIZ / "config" / "cidades" / f"{slug}.yaml").read_text("utf-8"))
    cod = cfg["cod_ibge"]
    s, bairros, nomes = zonas(cod, slug, cfg["n_zonas"])
    pop = s.groupby("zona")["pop"].sum()
    print("  " + ", ".join(f"{z}: {nomes[z]} ({p:,} hab.)" for z, p in pop.items()))

    indicadores = pd.concat([
        _seguranca(con, s, bairros, cod),
        _saude(con, cfg_estado, cfg, s, slug, rotear_de_novo),
        _infraestrutura(con, s),
        _natureza(cfg, s),
    ], ignore_index=True)
    _exportar(con, cfg, slug, s, bairros, nomes, indicadores)


def _exportar(con, cfg, slug, s, bairros, nomes, indicadores) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    extras = {"eventos": "eventos", "minutos": "minutos"}
    por_zona: dict[int, dict] = {}
    for linha in indicadores.to_dict("records"):
        if pd.isna(linha["valor"]):
            continue
        valor = {"valor": round(float(linha["valor"]), 3)}
        for coluna, chave in extras.items():
            if coluna in linha and pd.notna(linha[coluna]):
                valor[chave] = round(float(linha[coluna]), 3)
        por_zona.setdefault(int(linha["zona"]), {})[linha["indicador"]] = valor

    fontes = ["ssp_bo", "censo_setores", "rotas", "cnes", "mapbiomas"]
    anos_crime = int(indicadores["anos"].dropna().iloc[0])
    pop = s.groupby("zona")["pop"].sum()
    lista_bairros = bairros.groupby("zona")["nome"].apply(sorted).to_dict()
    dados = {
        "gerado_em": date.today().isoformat(),
        "coletas": [
            {"fonte": f, "coletado_em": c.isoformat(), "referencia": r}
            for f, c, r in con.execute("SELECT * FROM coletas ORDER BY fonte").fetchall() if f in fontes
        ],
        "config": {"topicos": cfg["topicos"], "filtros_apenas": cfg["filtros_apenas"], "corte": cfg["corte"]},
        "unidades": indicadores.drop_duplicates("indicador").set_index("indicador")["unidade"].to_dict(),
        "cidade": {"cod": cfg["cod_ibge"], "nome": cfg["nome"], "anos_crime": anos_crime},
        "municipios": [
            {
                "cod": int(z),
                "nome": nomes[z],
                "populacao": int(pop[z]),
                "regiao_imediata": cfg["nome"],
                "regiao_intermediaria": cfg["nome"],
                "bairros": lista_bairros.get(z, []),
                "indicadores": por_zona.get(int(z), {}),
            }
            for z in pop.index
        ],
    }
    (DESTINO / f"{slug}.json").write_text(json.dumps(dados, ensure_ascii=False, allow_nan=False), "utf-8")

    contorno = s.dissolve("zona").reset_index()[["zona", "geometry"]]
    contorno["geometry"] = contorno.simplify(15)  # metros: o arquivo cai para poucos KB sem mudar o desenho
    contorno = contorno.rename(columns={"zona": "cod"}).to_crs(4326)
    (DESTINO / f"{slug}.geojson").write_text(contorno.to_json(drop_id=True), "utf-8")

    # Índice das cidades detalhadas, para o app mostrar o botão "ver por dentro"
    indice = []
    for arquivo in sorted((RAIZ / "config" / "cidades").glob("*.yaml")):
        c = yaml.safe_load(arquivo.read_text("utf-8"))
        if (DESTINO / f"{arquivo.stem}.json").exists():
            indice.append({"cod": c["cod_ibge"], "slug": arquivo.stem, "nome": c["nome"]})
    (DESTINO / "index.json").write_text(json.dumps(indice, ensure_ascii=False), "utf-8")
    print(f"  exportado para {(DESTINO / slug).relative_to(RAIZ)}.json e .geojson")
