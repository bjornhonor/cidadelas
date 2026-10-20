"""Censo 2022 por setor censitário: água e esgoto dos domicílios (Agregados por Setores, Características do
Domicílio parte 2). Serve para o saneamento dentro de uma cidade (ver `cidade/`); o do estado vem do SINISA.

O arquivo é do Brasil todo; guarda só os setores de SP. Setor com poucos domicílios vem com "X" (sigilo).
"""

import zipfile

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/"
    "Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.zip"
)
AGUA = [f"V00{n}" for n in range(111, 119)]  # forma de abastecimento: soma = domicílios ocupados
AGUA_REDE = "V00111"  # rede geral de distribuição
ESGOTO_REDE = ["V00309", "V00310"]  # rede geral ou pluvial; fossa séptica ligada à rede


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    caminho = baixar("ibge", URL.rsplit("/", 1)[1], URL, forcar)
    with zipfile.ZipFile(caminho) as z:
        with z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, sep=";", dtype={"setor": str}, usecols=["setor", *AGUA, *ESGOTO_REDE])
    df = df[df["setor"].str.startswith("35")]
    numeros = df.columns.drop("setor")
    df[numeros] = df[numeros].apply(pd.to_numeric, errors="coerce")
    saida = pd.DataFrame({
        "cd_setor": df["setor"],
        "domicilios": df[AGUA].sum(axis=1, min_count=1),
        "agua_rede": df[AGUA_REDE],
        "esgoto_rede": df[ESGOTO_REDE].sum(axis=1, min_count=1),
    })
    con.execute("CREATE OR REPLACE TABLE censo_setor_saneamento AS SELECT * FROM saida")
    registrar_coleta(con, "censo_setores", "Censo 2022")
    print(f"  {len(saida):,} setores de SP; sem dado (sigilo): {saida['agua_rede'].isna().sum():,}")
