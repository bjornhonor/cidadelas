"""MapBiomas Coleção 10: mapa de cobertura do solo de 30 m, resumido numa grade de ~300 m cobrindo SP e arredores.

Lê só o recorte de SP do GeoTIFF do Brasil (~800 MB, em blocos, direto do bucket público) e grava, para cada
célula de 10×10 pixels, a fração de cada grupo de classes abaixo e de terra (o que não é água nem fora do mapa).
"""

import duckdb
import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

from ..db import registrar_coleta
from ..paths import RAW

ANO = 2024
URL = (
    "/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_10/lulc/coverage/"
    f"brazil_coverage_{ANO}.tif"
)
DESTINO = RAW / "mapbiomas" / f"grade_300m_{ANO}.npz"
GRUPOS = {
    "mata_nativa": [3, 4, 5, 6, 49],  # floresta, savana, mangue, floresta alagável, restinga arbórea
    "campo_nativo": [11, 12, 13, 29, 32, 50],  # área úmida, campo, afloramento, apicum, restinga herbácea...
    "silvicultura": [9],  # eucalipto, pinus
    "mosaico": [21],  # mistura de pasto, roça e mata que o satélite não separa (sítios, chácaras)
    "pastagem": [15],
    "lavoura": [18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48, 62],  # cana, soja, café, laranja...
    "urbana": [24],
}
FORA_DA_TERRA = [0, 31, 33]  # fora do mapa (mar, outro país), aquicultura, rio/lago/oceano
FATOR = 10  # pixels de 30 m por lado de cada célula da grade
# SP com folga para o raio das cidades de divisa (graus)
BBOX = (-53.5, -25.7, -43.8, -19.4)


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    if DESTINO.exists() and not forcar:
        print(f"  cache: {DESTINO.relative_to(RAW)}")
    else:
        _baixar_grade()
    con.execute("DROP TABLE IF EXISTS mapbiomas")  # tabela por município da versão anterior, sem uso
    registrar_coleta(con, "mapbiomas", f"Coleção 10, {ANO}")


def _baixar_grade() -> None:
    print(f"  lendo o recorte de SP do mapa de {ANO} (~800 MB, alguns minutos)")
    with rasterio.open(URL) as mapa:
        janela = from_bounds(*BBOX, mapa.transform).round_offsets().round_lengths()
        altura, largura = (int(janela.height) // FATOR) * FATOR, (int(janela.width) // FATOR) * FATOR
        grade = {k: np.zeros((altura // FATOR, largura // FATOR), np.float32) for k in [*GRUPOS, "terra"]}
        faixa = 256 * FATOR  # linhas lidas por vez: múltiplo do bloco interno de 256 px
        for i in range(0, altura, faixa):
            h = min(faixa, altura - i)
            pixels = mapa.read(1, window=Window(janela.col_off, janela.row_off + i, largura, h))
            mascaras = {nome: np.isin(pixels, classes) for nome, classes in GRUPOS.items()}
            mascaras["terra"] = ~np.isin(pixels, FORA_DA_TERRA)
            for nome, mascara in mascaras.items():
                grade[nome][i // FATOR:(i + h) // FATOR] = mascara.reshape(h // FATOR, FATOR, -1, FATOR).mean((1, 3))
            print(f"  {min(i + h, altura) * 100 // altura}%", end="\r")
        transformacao = mapa.window_transform(janela) * rasterio.Affine.scale(FATOR)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DESTINO, transformacao=np.array(transformacao)[:6], **grade)
