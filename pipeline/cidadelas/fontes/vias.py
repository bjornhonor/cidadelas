"""Quilômetros de rua urbana por município (OpenStreetMap) e frota de carros e motos (SENATRAN).

Rua urbana: trechos de via de uso local (primary a residential, sem rodovia expressa, serviço ou trilha) cujo ponto
do meio cai num setor censitário urbano de 2022. Rodovia de passagem e estrada rural não aguentam o trânsito da
cidade, por isso ficam de fora do denominador.
"""

import duckdb
import geopandas as gpd
import osmium
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar
from ..nomes import chave_nome
from ..paths import RAW

URL_FROTA = (
    "https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-2026-2/"
    "Frota_por_municipio_e_tipo_Agosto_2026.xlsx"
)
MES_FROTA = "08/2026"
TIPOS_FROTA = ["AUTOMOVEL", "CAMINHONETE", "CAMIONETA", "UTILITARIO", "MOTOCICLETA", "MOTONETA", "CICLOMOTOR"]
VIAS_LOCAIS = {
    "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link",
    "unclassified", "residential", "living_street",
}
SETOR_URBANO = ("1", "2", "3")  # CD_SIT do Censo 2022


class _Vias(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.trechos = []  # (km, lon, lat do nó do meio)

    def way(self, w):
        if w.tags.get("highway") not in VIAS_LOCAIS or len(w.nodes) < 2:
            return
        try:
            km = osmium.geom.haversine_distance(w.nodes) / 1000
            meio = w.nodes[len(w.nodes) // 2].location
            self.trechos.append((km, meio.lon, meio.lat))
        except osmium.InvalidLocationError:  # nó fora do recorte do estado
            pass


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    osm = RAW / "osm" / "sao-paulo-latest.osm.pbf"  # baixado por `coletar rotas`
    setores = RAW / "ibge" / "SP_setores_CD2022.gpkg"
    if not osm.exists() or not setores.exists():
        raise FileNotFoundError("rode `coletar rotas` antes: ele baixa o OpenStreetMap e os setores censitários")

    print("  lendo as ruas do OpenStreetMap (alguns minutos)")
    vias = _Vias()
    vias.apply_file(str(osm), locations=True, idx="flex_mem")
    trechos = pd.DataFrame(vias.trechos, columns=["km", "lon", "lat"])
    pontos = gpd.GeoDataFrame(trechos[["km"]], geometry=gpd.points_from_xy(trechos["lon"], trechos["lat"]), crs="EPSG:4326")

    todos = gpd.read_file(setores, columns=["CD_MUN", "CD_SIT", "v0001"])
    todos["urbano"] = todos["CD_SIT"].isin(SETOR_URBANO)
    todos["pop"] = pd.to_numeric(todos["v0001"], errors="coerce").fillna(0)
    # Parcela urbana da população: só os carros de quem mora na cidade disputam a rua urbana
    fracao_urbana = (
        todos.assign(pop_urbana=todos["pop"] * todos["urbano"]).groupby("CD_MUN")[["pop_urbana", "pop"]].sum()
        .pipe(lambda g: (g["pop_urbana"] / g["pop"]).rename("fracao_urbana")).reset_index()
    )
    fracao_urbana["cod_ibge"] = fracao_urbana.pop("CD_MUN").astype(int)
    urbanos = todos[todos["urbano"]].to_crs("EPSG:4326")
    dentro = gpd.sjoin(pontos, urbanos[["CD_MUN", "geometry"]], predicate="within", how="inner")
    km = dentro.groupby("CD_MUN")["km"].sum().rename("km_rua_urbana").reset_index()
    km["cod_ibge"] = km.pop("CD_MUN").astype(int)

    frota = pd.read_excel(baixar("senatran", "frota_municipio_2026-08.xlsx", URL_FROTA, forcar), header=3)
    frota = frota[frota["UF"] == "SP"]
    municipios = con.execute("SELECT cod_ibge, nome FROM municipios").df()
    por_chave = dict(zip(municipios["nome"].map(chave_nome), municipios["cod_ibge"]))
    # Os nomes casam com o IBGE depois de normalizar; a linha "MUNICIPIO NAO INFORMADO" fica sem código e sai
    frota = pd.DataFrame({
        "cod_ibge": frota["MUNICIPIO"].map(chave_nome).map(por_chave),
        "veiculos": frota[TIPOS_FROTA].sum(axis=1),
    })
    sem_par = municipios[~municipios["cod_ibge"].isin(frota["cod_ibge"])]
    if not sem_par.empty:
        raise ValueError(f"Municípios sem frota na SENATRAN: {sem_par['nome'].tolist()}")

    df = (
        municipios[["cod_ibge"]].merge(frota.dropna(), on="cod_ibge", how="left")
        .merge(km, on="cod_ibge", how="left").merge(fracao_urbana, on="cod_ibge", how="left")
    )
    con.execute("CREATE OR REPLACE TABLE vias AS SELECT * FROM df")
    registrar_coleta(con, "vias", f"OSM + frota SENATRAN {MES_FROTA}")
    print(f"  {len(trechos):,} trechos de via; {df['km_rua_urbana'].sum():,.0f} km de rua urbana; "
          f"{df['veiculos'].sum():,.0f} carros e motos")
