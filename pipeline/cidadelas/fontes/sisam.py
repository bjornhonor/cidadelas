"""SISAM (INPE + Ministério da Saúde): PM2.5 diário por município, estimado por satélite e modelo (reanálise, ~12 km).

Usa a mesma API do mapa de reanálise do site (https://data.inpe.br/queimadas/sisam/reanalise), que devolve um mês
de todos os municípios do estado por vez. Guarda a média de cada ano.
"""

import json

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

ANOS = range(2023, 2026)  # três anos, para um ano de queimada fora do comum não decidir sozinho
URL = (
    "https://data.inpe.br/queimadas/sisam/api/reanalise/map"
    "?estado=SP&data_inicio={inicio}&data_fim={fim}&poluente=pm25"
)


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    dias = []
    for ano in ANOS:
        for mes in range(1, 13):
            fim = (pd.Timestamp(ano, mes, 1) + pd.offsets.MonthEnd()).date()
            url = URL.format(inicio=f"{ano}-{mes:02d}-01", fim=fim)
            arquivo = baixar("sisam", f"pm25_sp_{ano}_{mes:02d}.json", url, forcar, silencioso=True, pausa=1)
            dias.extend(json.loads(arquivo.read_text("utf-8"))["municipios"])
        print(f"  {ano}")
    df = pd.DataFrame(dias)
    df = pd.DataFrame({
        "cod_ibge": df["CD_MUN"].astype(int),
        "ano": pd.to_datetime(df["data"]).dt.year,
        "pm25": df["pm2_5_reanalise"],
    }).groupby(["cod_ibge", "ano"], as_index=False).agg(pm25=("pm25", "mean"), dias=("pm25", "count"))
    con.execute("CREATE OR REPLACE TABLE sisam_pm25 AS SELECT * FROM df")
    registrar_coleta(con, "sisam", f"reanálise PM2.5 {ANOS.start}-{ANOS.stop - 1}")
    print(f"  {df['cod_ibge'].nunique()} municípios; PM2.5 médio {df['pm25'].min():.1f}–{df['pm25'].max():.1f} µg/m³")
