from datetime import date

import duckdb

from .paths import BANCO


def conectar() -> duckdb.DuckDBPyConnection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(BANCO))
    con.execute("""
        CREATE TABLE IF NOT EXISTS coletas (
            fonte      VARCHAR PRIMARY KEY,
            coletado_em DATE,
            referencia VARCHAR  -- período coberto pelos dados, ex.: "Censo 2022"
        )
    """)
    return con


def registrar_coleta(con: duckdb.DuckDBPyConnection, fonte: str, referencia: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO coletas VALUES (?, ?, ?)",
        [fonte, date.today(), referencia],
    )
