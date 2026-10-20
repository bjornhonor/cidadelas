"""SSP-SP: microdados dos boletins de ocorrência (portal "SP Dados Criminais"), só os crimes violentos.

Cada linha é uma natureza registrada num BO, com bairro, logradouro e coordenada de onde aconteceu. Serve para
contar crime dentro de uma cidade (ver `cidade/`). Quando o crime é em residência, a SSP omite logradouro e
coordenada ("vedação da divulgação"), mas mantém o bairro.

Os arquivos são planilhas de ~200 MB por ano, com uma aba por semestre. Guarda o estado todo, para poder
detalhar outras cidades depois.
"""

import duckdb
import numpy as np
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

URL = "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{ano}.xlsx"
ANOS = range(2022, 2026)  # o portal começa em 2022

# Natureza apurada (sem acento, maiúscula) -> indicador. Mesmos crimes de calculo/seguranca.py
NATUREZAS = {
    "HOMICIDIO DOLOSO": "crimes_letais",
    "TENTATIVA DE HOMICIDIO": "crimes_letais",
    "LATROCINIO": "crimes_letais",
    "LESAO CORPORAL SEGUIDA DE MORTE": "crimes_letais",
    "ROUBO - OUTROS": "roubo",
    "ROUBO DE VEICULO": "roubo",
}
COLUNAS = {
    "CD_IBGE": "cod_ibge", "ANO_ESTATISTICA": "ano", "NUM_BO": "num_bo", "ANO_BO": "ano_bo",
    "NOME_DELEGACIA": "delegacia", "NATUREZA_APURADA": "natureza", "BAIRRO": "bairro",
    "DESCR_SUBTIPOLOCAL": "tipo_local", "LATITUDE": "lat", "LONGITUDE": "lon",
}


def _sem_acento(s: pd.Series) -> pd.Series:
    return s.astype(str).str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").str.upper().str.strip()


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    partes = []
    for ano in ANOS:
        caminho = baixar("ssp", f"SPDadosCriminais_{ano}.xlsx", URL.format(ano=ano), forcar)
        planilha = pd.ExcelFile(caminho, engine="calamine")
        for aba in planilha.sheet_names:
            if aba.startswith("CAMPOS"):  # dicionário de dados
                continue
            df = planilha.parse(aba, usecols=list(COLUNAS)).rename(columns=COLUNAS)
            df["natureza"] = _sem_acento(df["natureza"])
            df = df[df["natureza"].isin(NATUREZAS)].copy()
            df["indicador"] = df["natureza"].map(NATUREZAS)
            partes.append(df)
        print(f"  {ano}: {sum(len(p) for p in partes):,} registros violentos até aqui")

    df = pd.concat(partes, ignore_index=True)
    # Algumas abas trazem coordenada como texto, com vírgula decimal ou "NULL"
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df["cod_ibge"] = pd.to_numeric(df["cod_ibge"], errors="coerce").astype("Int64")
    # Coordenada zero ou fora de SP é coordenada ausente
    fora = ~(df["lat"].between(-25.5, -19.5) & df["lon"].between(-53.5, -44))
    df.loc[fora, ["lat", "lon"]] = np.nan
    df["bairro"] = df["bairro"].where(df["bairro"].notna(), None)
    df["num_bo"] = df["num_bo"].astype(str)
    # Um BO pode repetir a mesma natureza (uma linha por vítima ou autor): conta uma ocorrência
    df = df.drop_duplicates(["num_bo", "ano_bo", "delegacia", "natureza"])
    df = df[["cod_ibge", "ano", "indicador", "natureza", "bairro", "tipo_local", "lat", "lon"]]

    con.execute("CREATE OR REPLACE TABLE ssp_bo AS SELECT * FROM df")
    registrar_coleta(con, "ssp_bo", f"{ANOS.start}-{ANOS.stop - 1}")
    print(f"  {len(df):,} ocorrências; {df['lat'].notna().mean():.0%} com coordenada, "
          f"{df['bairro'].notna().mean():.0%} com bairro")
