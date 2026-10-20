from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data"
RAW = DADOS / "raw"
BANCO = DADOS / "cidadelas.duckdb"
CONFIG = RAIZ / "config" / "ranking.yaml"
