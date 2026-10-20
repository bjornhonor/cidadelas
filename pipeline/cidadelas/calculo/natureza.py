"""Natureza: verde perto de onde as pessoas moram, quanto do entorno é cidade, ar e árvores na rua.

Verde = mata (nativa ou plantada), campo nativo e mosaico de sítios e chácaras: o que se vê como paisagem verde.
Cana, soja, café e pasto de gado não contam, senão a planície de lavoura do interior empataria com a serra.

Verde e área urbana são medidas a partir de cada setor censitário habitado: % da terra num raio em volta dele
(grade de ~300 m do MapBiomas), e a média do município é pesada pela população de cada setor. Assim a mata do
extremo sul da capital não conta para quem mora no centro, e um município grande com a cidade encostada numa
serra é medido pela serra, não pelo pasto do outro lado.
"""

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio import Affine
from scipy.signal import fftconvolve

from ..fontes.mapbiomas import DESTINO as GRADE
from ..paths import RAW

SETORES = RAW / "ibge" / "SP_setores_CD2022.gpkg"  # baixado por `coletar rotas`
KM_POR_GRAU = 111.32
LATITUDE_MEDIA = -22.5  # centro de SP, para converter graus de longitude em km
VERDE = ["mata_nativa", "silvicultura", "campo_nativo", "mosaico"]  # grupos de fontes/mapbiomas.py


def _disco(raio_km: float, transformacao: Affine) -> np.ndarray:
    dx = transformacao.a * KM_POR_GRAU * np.cos(np.radians(LATITUDE_MEDIA))
    dy = -transformacao.e * KM_POR_GRAU
    rx, ry = int(raio_km / dx) + 1, int(raio_km / dy) + 1
    y, x = np.mgrid[-ry:ry + 1, -rx:rx + 1]
    return ((x * dx) ** 2 + (y * dy) ** 2 <= raio_km ** 2).astype(np.float32)


def percentual_no_raio(lon: np.ndarray, lat: np.ndarray, medidas: dict[str, tuple[list[str], float]]) -> dict[str, np.ndarray]:
    """Para cada ponto, % da terra no raio ocupada pelos grupos de classe. medidas: indicador -> (grupos, raio em km)."""
    grade = np.load(GRADE)
    transformacao = Affine(*grade["transformacao"])
    col, lin = (~transformacao) * (lon, lat)
    col, lin = col.astype(int), lin.astype(int)
    resultado = {}
    for indicador, (grupos, raio) in medidas.items():
        disco = _disco(raio, transformacao)
        # % da terra no raio (água e mar fora da conta, senão cidade de praia perde para o oceano)
        classe_no_raio = fftconvolve(sum(grade[g] for g in grupos), disco, mode="same")[lin, col]
        terra_no_raio = fftconvolve(grade["terra"], disco, mode="same")[lin, col]
        resultado[indicador] = 100 * np.clip(classe_no_raio / np.maximum(terra_no_raio, 1e-6), 0, 1)
    return resultado


def _perto_de_casa(cfg: dict) -> pd.DataFrame:
    setores = gpd.read_file(SETORES, columns=["CD_MUN", "v0001"])
    setores = setores[setores["v0001"] > 0]
    ponto = setores.geometry.representative_point()

    natureza = cfg["topicos"]["natureza"]
    medidas = {
        "verde_perto": (VERDE, natureza["raio_perto_km"]),
        "verde_regiao": (VERDE, natureza["raio_regiao_km"]),
        "area_urbana": (["urbana"], natureza["raio_perto_km"]),
    }
    por_setor = pd.DataFrame({
        "cod_ibge": setores["CD_MUN"].astype(int).to_numpy(), "pop": setores["v0001"].to_numpy(),
        **percentual_no_raio(ponto.x.to_numpy(), ponto.y.to_numpy(), medidas),
    })

    unidades = {
        "verde_perto": f"% de mata, campo ou sítio a até {medidas['verde_perto'][1]} km de casa (média dos moradores)",
        "verde_regiao": f"% de mata, campo ou sítio a até {medidas['verde_regiao'][1]} km de casa (média dos moradores)",
        "area_urbana": f"% de área urbanizada a até {medidas['area_urbana'][1]} km de casa (média dos moradores)",
    }
    media = por_setor.groupby("cod_ibge").apply(
        lambda g: pd.Series({i: np.average(g[i], weights=g["pop"]) for i in medidas}), include_groups=False,
    )
    return (
        media.reset_index()
        .melt(id_vars="cod_ibge", var_name="indicador", value_name="valor")
        .assign(unidade=lambda d: d["indicador"].map(unidades))
    )


def calcular(con: duckdb.DuckDBPyConnection, cfg: dict) -> pd.DataFrame:
    partes = [_perto_de_casa(cfg)]

    # A reanálise sem calibração superestima o valor absoluto (capital 2025: 36 contra 13 da série calibrada com
    # estações), mas serve para comparar cidades, que é o que a nota faz
    ar = con.execute("SELECT cod_ibge, avg(pm25) AS valor, min(ano) AS de, max(ano) AS ate FROM sisam_pm25 GROUP BY 1").df()
    partes.append(ar[["cod_ibge", "valor"]].assign(
        indicador="ar_pm25",
        unidade=f"PM2.5 estimado por satélite, média {ar['de'].min()}–{ar['ate'].max()} (serve para comparar cidades, "
                "não para ler em µg/m³)",
    ))

    # Índice de arborização 0–100: domicílio com 1–2 árvores na face de quadra vale 1/3, 3–4 vale 2/3, 5+ vale 1
    arvores = con.execute("""
        SELECT cod_ibge, 100 * (arvores_1_2 / 3 + 2 * arvores_3_4 / 3 + arvores_5_mais) / total AS valor
        FROM censo_entorno WHERE total > 0
    """).df()
    partes.append(arvores.assign(
        indicador="arborizacao", unidade="índice de árvores na rua de casa (0 = nenhuma, 100 = 5 ou mais em todas)",
    ))
    return pd.concat(partes, ignore_index=True).assign(topico="natureza")
