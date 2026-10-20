"""Atlas Digital de Desastres no Brasil (MIDR): desastres registrados no S2iD por município, 1991–2025.

Base completa em https://atlasdigital.mdr.gov.br/paginas/downloads.xhtml. Registro depende de a prefeitura
notificar a Defesa Civil, então cidade que registra mais pode parecer pior do que é.
"""

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

URL = "https://atlasdigital.mdr.gov.br/arquivos/2026/BD_Atlas_1991_2025_v1.1_2026.08.06_Consolidado.csv"
COLUNAS_DANOS = ["DH_MORTOS", "DH_FERIDOS", "DH_DESABRIGADOS", "DH_DESALOJADOS"]


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    caminho = baixar("atlas_desastres", "atlas_1991_2025.csv", URL, forcar)
    df = pd.read_csv(caminho, sep=";", encoding="cp1252", dtype=str)
    df = df[df["Sigla_UF"] == "SP"]
    eventos = pd.DataFrame({
        "cod_ibge": pd.to_numeric(df["Cod_IBGE_Mun"]).astype(int),
        "data": pd.to_datetime(df["Data_Evento"], format="%d/%m/%Y", errors="coerce"),
        "cobrade": df["Cod_Cobrade"],
        "tipo": df["descricao_tipologia"],
        "grupo": df["grupo_de_desastre"],
        **{c.lower(): pd.to_numeric(df[c].str.replace(",", "."), errors="coerce").fillna(0) for c in COLUNAS_DANOS},
    })
    con.execute("CREATE OR REPLACE TABLE desastres AS SELECT * FROM eventos")
    registrar_coleta(con, "desastres", f"{eventos['data'].dt.year.min()}-{eventos['data'].dt.year.max()}")
    print(f"  {len(eventos)} registros em {eventos['cod_ibge'].nunique()} municípios")
