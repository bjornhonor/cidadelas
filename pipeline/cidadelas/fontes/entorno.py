"""Censo 2022, Pesquisa Urbanística do Entorno dos Domicílios (SIDRA 9583): como é a rua em frente de casa.

Percentual de domicílios (em setores urbanos pesquisados) com via pavimentada, bueiro, iluminação pública,
calçada, calçada sem obstáculo, e quantas árvores há na face de quadra.
"""

import json

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

CATEGORIAS = {
    "200": "total",
    "72246": "pavimentada",
    "72250": "bueiro",
    "72254": "iluminacao",
    "72266": "calcada",
    "72271": "calcada_sem_obstaculo",
    "72278": "arvores_0",
    "72279": "arvores_1_2",
    "72280": "arvores_3_4",
    "72281": "arvores_5_mais",
}
URL = (
    "https://apisidra.ibge.gov.br/values/t/9583/n6/in%20n3%2035/v/9599/p/2022/c125/2932/c14/"
    + ",".join(CATEGORIAS)
)


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    dados = json.loads(baixar("ibge", "entorno_censo2022.json", URL, forcar).read_text("utf-8"))[1:]
    df = pd.DataFrame([
        {"cod_ibge": int(d["D1C"]), "categoria": CATEGORIAS[d["D5C"]], "domicilios": pd.to_numeric(d["V"], errors="coerce")}
        for d in dados
    ]).pivot(index="cod_ibge", columns="categoria", values="domicilios").reset_index()
    con.execute("CREATE OR REPLACE TABLE censo_entorno AS SELECT * FROM df")
    registrar_coleta(con, "entorno", "Censo 2022")
    print(f"  {len(df)} municípios; sem setor pesquisado: {int((df['total'].fillna(0) == 0).sum())}")
