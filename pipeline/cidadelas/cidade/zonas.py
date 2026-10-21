"""Divide uma cidade em zonas de população parecida, juntando setores censitários vizinhos.

O IBGE não tem bairros para a maioria das cidades (em Valinhos o campo vem vazio), então as zonas saem dos
setores do Censo 2022:

1. Sementes: k-means pesado pela população dá o centro de cada zona.
2. Crescimento: a zona com menos gente anexa o setor vizinho (que encosta nela) mais perto da sua semente, até não
   sobrar setor. Assim toda zona é contínua e as populações ficam parecidas.
3. Nome: os bairros do OpenStreetMap que caem dentro da zona, do mais perto do centro para o mais longe.

A divisão fica gravada em config/cidades/<cidade>_setores.csv. Rodar de novo reaproveita o arquivo, então dá para
editar à mão (mudar um setor de zona) ou apagar para gerar outra.
"""

import geopandas as gpd
import numpy as np
import osmium
import pandas as pd
from sklearn.cluster import KMeans

from ..nomes import chave_nome
from ..paths import RAIZ, RAW

SETORES = RAW / "ibge" / "SP_setores_CD2022.gpkg"
OSM = RAW / "osm" / "sao-paulo-latest.osm.pbf"
CRS_METROS = 31983  # SIRGAS 2000 / UTM 23S
LUGARES = {"suburb", "quarter", "neighbourhood"}
FOLGA_DIVISA_M = 1_000


def setores(cod_ibge: int) -> gpd.GeoDataFrame:
    s = gpd.read_file(SETORES, where=f"CD_MUN = '{cod_ibge}'", columns=["CD_SETOR", "CD_SIT", "NM_NU", "v0001"])
    s = s.rename(columns={"CD_SETOR": "cd_setor", "CD_SIT": "situacao", "NM_NU": "nucleo", "v0001": "pop"})
    s["pop"] = pd.to_numeric(s["pop"], errors="coerce").fillna(0).astype(int)
    return s.to_crs(CRS_METROS)


def _crescer(s: gpd.GeoDataFrame, n_zonas: int) -> np.ndarray:
    centro = s.geometry.representative_point()
    xy = np.c_[centro.x, centro.y]
    peso = s["pop"].to_numpy() + 1  # setor sem morador também precisa de zona
    sementes = KMeans(n_zonas, n_init=10, random_state=0).fit(xy, sample_weight=peso).cluster_centers_
    # Vizinhos: setores que se tocam (1 m de folga para frestas da malha)
    toques = gpd.sjoin(s[["geometry"]].assign(geometry=s.buffer(1)), s[["geometry"]], predicate="intersects")
    vizinhos = toques[toques.index != toques["index_right"]].groupby(level=0)["index_right"].apply(set).to_dict()

    zona = np.full(len(s), -1)
    pop = np.zeros(n_zonas)
    for z, c in enumerate(sementes):
        livres = np.flatnonzero(zona < 0)
        i = livres[np.argmin(np.hypot(*(xy[livres] - c).T))]
        zona[i] = z
        pop[z] += peso[i]
    while (zona < 0).any():
        for z in np.argsort(pop):  # a menor zona com fronteira livre cresce primeiro
            fronteira = {v for i in np.flatnonzero(zona == z) for v in vizinhos.get(i, ())} - set(np.flatnonzero(zona >= 0))
            if fronteira:
                f = np.array(sorted(fronteira))
                i = f[np.argmin(np.hypot(*(xy[f] - sementes[z]).T))]
                zona[i] = z
                pop[z] += peso[i]
                break
        else:  # setor ilhado (sem vizinho com zona): vai para a zona da semente mais perto
            i = np.flatnonzero(zona < 0)[0]
            zona[i] = int(np.argmin(np.hypot(*(sementes - xy[i]).T)))
            pop[zona[i]] += peso[i]
    # Numera do norte para o sul, para a ordem ser estável e fácil de achar no mapa
    norte = pd.Series(xy[:, 1]).groupby(zona).mean().sort_values(ascending=False).index
    return pd.Series(range(1, n_zonas + 1), index=norte)[zona].to_numpy()


class _Lugares(osmium.SimpleHandler):
    def __init__(self, caixa):
        super().__init__()
        self.caixa = caixa
        self.lugares = []

    def node(self, n):
        if n.tags.get("place") in LUGARES and "name" in n.tags:
            lon, lat = n.location.lon, n.location.lat
            x0, y0, x1, y1 = self.caixa
            if x0 <= lon <= x1 and y0 <= lat <= y1:
                self.lugares.append((n.tags["name"], lon, lat))


def bairros_osm(s: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Pontos de bairro do OpenStreetMap na cidade, com a zona do setor mais perto (o OSM quase não tem o contorno
    dos bairros). Vale ponto até FOLGA_DIVISA_M além da divisa: bairro de beira de divisa às vezes cai do outro lado.
    """
    leitor = _Lugares(s.to_crs(4326).total_bounds + np.array([-0.05, -0.05, 0.05, 0.05]))
    leitor.apply_file(str(OSM))
    df = pd.DataFrame(leitor.lugares, columns=["nome", "lon", "lat"])
    pontos = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326).to_crs(CRS_METROS)
    pontos = gpd.sjoin_nearest(pontos, s[["zona", "geometry"]], max_distance=FOLGA_DIVISA_M, distance_col="fora_m")
    # Só depois de filtrar pela cidade: "Centro" existe em Valinhos, Campinas e Vinhedo
    return pontos.sort_values("fora_m").drop_duplicates("nome").drop(columns="index_right").reset_index(drop=True)


def _nomes(s: gpd.GeoDataFrame, bairros: gpd.GeoDataFrame) -> dict[int, str]:
    nomes = {}
    for z, g in s.groupby("zona"):
        centro = g.dissolve().geometry.iloc[0].representative_point()
        dentro = bairros[bairros["zona"] == z]
        ordem = []
        for nome in dentro.assign(d=dentro.distance(centro)).sort_values("d")["nome"]:
            # "Chácaras Alpina" e "Chácaras Alpinas" são o mesmo lugar
            if not any(chave_nome(nome)[:12] == chave_nome(o)[:12] for o in ordem):
                ordem.append(nome)
        rural = g.loc[g["situacao"] == "8", "pop"].sum() > g["pop"].sum() / 2
        base = " / ".join(ordem[:2]) if ordem else f"Zona {z}"
        nomes[int(z)] = f"{base} (rural)" if rural else base
    return nomes


def zonas(cod_ibge: int, slug: str, n_zonas: int) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[int, str]]:
    """Setores com a zona de cada um, pontos de bairro do OSM com a zona, e o nome de cada zona."""
    s = setores(cod_ibge)
    arquivo = RAIZ / "config" / "cidades" / f"{slug}_setores.csv"
    if arquivo.exists():
        divisao = pd.read_csv(arquivo, dtype={"cd_setor": str}).set_index("cd_setor")["zona"]
        faltando = set(s["cd_setor"]) - set(divisao.index)
        if faltando:
            raise ValueError(f"{arquivo.name}: {len(faltando)} setores sem zona, ex.: {sorted(faltando)[:3]}")
        s["zona"] = s["cd_setor"].map(divisao).astype(int)
        print(f"  zonas: {arquivo.relative_to(RAIZ)}")
    else:
        s["zona"] = _crescer(s, n_zonas)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        s[["cd_setor", "zona"]].sort_values(["zona", "cd_setor"]).to_csv(arquivo, index=False)
        print(f"  zonas novas gravadas em {arquivo.relative_to(RAIZ)}")
    bairros = bairros_osm(s)
    # Núcleos urbanos que o próprio Censo nomeia (loteamentos e chácaras afastados) também viram bairro
    nucleos = s.dropna(subset=["nucleo"]).assign(geometry=lambda d: d.representative_point()).drop_duplicates("nucleo")
    nucleos = nucleos[~nucleos["nucleo"].map(chave_nome).isin(bairros["nome"].map(chave_nome))]
    bairros = pd.concat([bairros, nucleos.rename(columns={"nucleo": "nome"})[["nome", "zona", "geometry"]]], ignore_index=True)
    return s, bairros, _nomes(s, bairros[bairros["fora_m"].fillna(0) == 0])
