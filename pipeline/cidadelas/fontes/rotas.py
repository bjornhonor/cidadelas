"""Tempo de carro de onde a população mora até as unidades de saúde.

- Origens: os 103 mil setores censitários de 2022 agrupados, dentro de cada município, em até 20 pontos pesados
  pela população (k-means). A capital vira 20 pontos; uma cidade de 3 mil habitantes vira 1.
- Destinos: unidades do CNES (SUS e particulares) com médico, leito, pronto-socorro ou equipamento de imagem. Para a
  capacidade, as unidades são agrupadas em quadrados de ~100 m (prédios de consultórios viram um destino só).
- Coordenadas: o CNES tem unidades marcadas em outra cidade (ex.: os grandes hospitais de Sorocaba aparecem perto de
  Alumínio). Unidade a mais de 8 km de qualquer ponto habitado do próprio município vai para o ponto mais populoso dele.
- Rotas: r5py (motor R5, precisa de Java 21) sobre o recorte de SP do OpenStreetMap. É velocidade de via livre,
  sem trânsito. Unidades de estados vizinhos ficam de fora (o mapa viário é só de SP).

É a etapa mais pesada do pipeline (minutos). Depende de `coletar ibge` e `coletar cnes`.
"""

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from ..db import registrar_coleta
from ..download import baixar

URL_OSM = "https://download.openstreetmap.fr/extracts/south-america/brazil/southeast/sao-paulo-latest.osm.pbf"
URL_SETORES = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/"
    "malha_com_atributos/setores/gpkg/UF/SP/SP_setores_CD2022.gpkg"
)
PESSOAS_POR_PONTO = 25_000
MAX_PONTOS_POR_MUNICIPIO = 20
# Duas buscas: acesso (unidade mais próxima; a curva de emergência zera em 90 min) e capacidade (raio do E2SFCA).
# O custo de cada busca cresce muito com o tempo máximo, por isso a de 90 min vai só até hospitais e PS.
TEMPO_ACESSO = timedelta(minutes=90)
TEMPO_CAPACIDADE = timedelta(minutes=30)
LIMITE_COORDENADA_KM = 8
CELULA_GRAUS = 0.001  # ~110 m
THREADS = 8  # o r5py roteia uma origem por vez; em paralelo fica ~5x mais rápido
ORIGENS_POR_LOTE = 20


def _origens(caminho_setores) -> pd.DataFrame:
    setores = gpd.read_file(caminho_setores, columns=["CD_MUN", "v0001"])
    setores = setores[pd.to_numeric(setores["v0001"], errors="coerce").fillna(0) > 0]
    pontos = setores.geometry.representative_point()
    df = pd.DataFrame({
        "cod_ibge": setores["CD_MUN"].astype(int).to_numpy(),
        "pop": pd.to_numeric(setores["v0001"]).to_numpy(),
        "lon": pontos.x.to_numpy(),
        "lat": pontos.y.to_numpy(),
    })

    grupos = []
    for cod, g in df.groupby("cod_ibge"):
        k = min(MAX_PONTOS_POR_MUNICIPIO, max(1, math.ceil(g["pop"].sum() / PESSOAS_POR_PONTO)), len(g))
        xy = g[["lon", "lat"]].to_numpy()
        # Distorção de longitude desprezível para agrupar pontos dentro de um município
        rotulos = KMeans(n_clusters=k, n_init=4, random_state=0).fit_predict(xy, sample_weight=g["pop"]) if k > 1 else np.zeros(len(g), int)
        for r in range(k):
            s = g[rotulos == r]
            peso = s["pop"].to_numpy()
            grupos.append({
                "cod_ibge": cod,
                "pop": int(peso.sum()),
                "lon": float(np.average(s["lon"], weights=peso)),
                "lat": float(np.average(s["lat"], weights=peso)),
            })
    origens = pd.DataFrame(grupos)
    origens.insert(0, "id", range(len(origens)))
    return origens


def _corrigir_coordenadas(unidades: pd.DataFrame, origens: pd.DataFrame) -> pd.DataFrame:
    pares = unidades.merge(origens[["cod_ibge", "lat", "lon"]], on="cod_ibge", suffixes=("", "_o"))
    pares["km"] = np.hypot(
        (pares["lat"] - pares["lat_o"]) * 111, (pares["lon"] - pares["lon_o"]) * 111 * np.cos(np.radians(pares["lat"]))
    )
    distante = pares.groupby("co_unidade")["km"].min() > LIMITE_COORDENADA_KM
    principal = origens.sort_values("pop").drop_duplicates("cod_ibge", keep="last").set_index("cod_ibge")
    u = unidades.assign(corrigida=unidades["co_unidade"].map(distante).fillna(False).astype(bool))
    u.loc[u["corrigida"], "lat"] = u.loc[u["corrigida"], "cod_ibge"].map(principal["lat"])
    u.loc[u["corrigida"], "lon"] = u.loc[u["corrigida"], "cod_ibge"].map(principal["lon"])
    return u


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    # r5py sobe uma JVM ao ser importado: só importa aqui, não quando o pipeline carrega
    import r5py

    osm = baixar("osm", "sao-paulo-latest.osm.pbf", URL_OSM, forcar)
    setores = baixar("ibge", "SP_setores_CD2022.gpkg", URL_SETORES, forcar)

    print("  agrupando setores censitários em pontos de origem")
    origens = _origens(setores)
    con.execute("CREATE OR REPLACE TABLE rotas_origens AS SELECT * FROM origens")
    print(f"  {len(origens)} pontos de origem, {origens['pop'].sum():,} habitantes")

    # Todas as redes: o cálculo de saúde filtra SUS ou SUS + particular sem precisar rotear de novo
    unidades = con.execute("""
        SELECT co_unidade, cod_ibge, lat, lon,
               tipo_unidade IN ('05', '07', '15', '20', '21', '73')
                 OR co_unidade IN (SELECT co_unidade FROM cnes_equipamentos WHERE tipo = '1' AND codigo = '10') AS acesso
        FROM cnes_unidades
        WHERE co_unidade IN (SELECT co_unidade FROM cnes_medicos)
           OR co_unidade IN (SELECT co_unidade FROM cnes_leitos WHERE qt_exist > 0)
           OR co_unidade IN (SELECT co_unidade FROM cnes_equipamentos WHERE tipo = '1' AND qt_exist > 0)
           OR tipo_unidade IN ('05', '07', '15', '20', '21', '73')
    """).df()
    unidades = _corrigir_coordenadas(unidades, origens)
    print(f"  {unidades['corrigida'].sum()} unidades com coordenada fora do município, movidas para o centro dele")
    # Capacidade: cada unidade cai numa célula; acesso: hospitais, prontos-socorros e hemodinâmica, um a um
    unidades["celula"] = (
        "c" + (unidades["lat"] / CELULA_GRAUS).round().astype(int).astype(str)
        + "_" + (unidades["lon"] / CELULA_GRAUS).round().astype(int).astype(str)
    )
    con.execute("CREATE OR REPLACE TABLE rotas_destinos AS SELECT co_unidade, celula, lat, lon, corrigida FROM unidades")
    destinos_capacidade = (
        unidades.groupby("celula", as_index=False)[["lat", "lon"]].mean().rename(columns={"celula": "id"})
    )
    destinos_acesso = unidades.loc[unidades["acesso"], ["co_unidade", "lat", "lon"]].rename(columns={"co_unidade": "id"})
    print(f"  destinos: {len(destinos_acesso)} para acesso, {len(destinos_capacidade)} células para capacidade")

    print("  montando a rede viária (demora alguns minutos na primeira vez)")
    rede = r5py.TransportNetwork(osm)

    def gdf(df):
        return gpd.GeoDataFrame(df[["id"]], geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")

    def matriz(destinos: pd.DataFrame, tempo_maximo: timedelta, rotulo: str) -> pd.DataFrame:
        lotes = [origens.iloc[i:i + ORIGENS_POR_LOTE] for i in range(0, len(origens), ORIGENS_POR_LOTE)]
        feitos = 0

        def rotear(lote):
            nonlocal feitos
            m = r5py.TravelTimeMatrix(
                rede, origins=gdf(lote), destinations=gdf(destinos),
                transport_modes=[r5py.TransportMode.CAR],
                departure=datetime(2026, 9, 1, 10, 0),  # só importa para transporte público
                max_time=tempo_maximo,
            )
            feitos += len(lote)
            print(f"    {rotulo}: {feitos}/{len(origens)} origens", flush=True)
            return pd.DataFrame(m).dropna(subset=["travel_time"])

        with ThreadPoolExecutor(THREADS) as executor:
            return pd.concat(executor.map(rotear, lotes), ignore_index=True)

    print("  calculando tempos de carro")
    tempos = pd.concat([
        matriz(destinos_acesso, TEMPO_ACESSO, "acesso"),
        matriz(destinos_capacidade, TEMPO_CAPACIDADE, "capacidade"),
    ], ignore_index=True)
    tempos = (
        tempos.rename(columns={"from_id": "origem", "to_id": "destino", "travel_time": "minutos"})
        .groupby(["origem", "destino"], as_index=False)["minutos"].min()
    )
    con.execute("CREATE OR REPLACE TABLE rotas_tempos AS SELECT * FROM tempos")

    registrar_coleta(con, "rotas", "OSM SP + CNES (SUS e particular)")
    print(f"  {len(tempos):,} pares origem-destino")
