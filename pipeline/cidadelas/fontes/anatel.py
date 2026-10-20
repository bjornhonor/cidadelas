"""Anatel: acessos de banda larga fixa por fibra óptica, pessoa física, por município (mês mais recente).

Arquivo de ~1 GB com todo o histórico (https://informacoes.anatel.gov.br/paineis/acessos/banda-larga-fixa);
usa só a planilha do ano corrente, com um mês por coluna.
"""

import zipfile

import duckdb

from ..db import registrar_coleta
from ..download import baixar
from ..paths import RAW

URL = "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/acessos/acessos_banda_larga_fixa.zip"
ANO = 2026


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    zip_path = baixar("anatel", "acessos_banda_larga_fixa.zip", URL, forcar)
    nome = f"Acessos_Banda_Larga_Fixa_{ANO}_Colunas.csv"
    csv = RAW / "anatel" / nome
    if forcar or not csv.exists():
        with zipfile.ZipFile(zip_path) as z:
            z.extract(nome, csv.parent)

    fonte = f"read_csv('{csv.as_posix()}', delim=';', all_varchar=true, header=true)"
    mes = max(c for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM {fonte})").fetchall() if c.startswith(f"{ANO}-"))
    con.execute(f"""
        CREATE OR REPLACE TABLE anatel_fibra AS
        SELECT "Código IBGE Município"::INTEGER AS cod_ibge, sum(coalesce(try_cast("{mes}" AS INTEGER), 0)) AS acessos_fibra
        FROM {fonte}
        WHERE UF = 'SP' AND "Meio de Acesso" = 'Fibra' AND "Tipo de Pessoa" = 'Pessoa Física'
        GROUP BY 1
    """)
    registrar_coleta(con, "anatel", mes)
    n, total = con.execute("SELECT count(*), sum(acessos_fibra) FROM anatel_fibra").fetchone()
    print(f"  {n} municípios, {total:,} acessos de fibra residenciais em {mes}")
