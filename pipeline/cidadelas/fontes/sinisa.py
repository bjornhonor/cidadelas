"""SINISA (Ministério das Cidades, sucessor do SNIS): tarifa média de água e esgoto e atendimento por município.

A "receita operacional direta média" (R$/m³ faturado) é o que o SNIS chamava de tarifa média. Ano de referência 2024.
"""

import io
import zipfile

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

BASE = "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/sinisa/resultados-sinisa"
URL_AGUA = f"{BASE}/SINISA_Resultados_Ref2024.zip"
URL_ESGOTO = f"{BASE}/SINISA_ESGOTO_Planilhas_2024.zip"

# Código do indicador → coluna no banco
INDICADORES_AGUA = {"IFA1001": "tarifa_agua_m3", "IAG0001": "atendimento_agua_pct"}
INDICADORES_ESGOTO = {
    "IFE1001": "tarifa_esgoto_m3",
    "IES0001": "atendimento_esgoto_pct",  # população com rede coletora
    "IES0007": "esgoto_tratado_pct",      # domicílios com coleta e tratamento
}


def _planilha(zip_path, trecho_nome: str, codigos: dict[str, str]) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        nome = next(n for n in z.namelist() if trecho_nome in n and n.endswith(".xlsx"))
        bruto = pd.read_excel(io.BytesIO(z.read(nome)), sheet_name=0, header=None)
    # A linha com os códigos (cod_IBGE, IAG0001, ...) vira o cabeçalho; os dados começam logo abaixo
    linha_codigos = bruto.index[bruto.iloc[:, 0].astype(str).str.strip() == "cod_IBGE"][0]
    df = bruto.iloc[linha_codigos + 1:].copy()
    df.columns = bruto.iloc[linha_codigos].astype(str).str.strip()
    faltando = set(codigos) - set(df.columns)
    if faltando:
        raise ValueError(f"{nome}: colunas não encontradas {faltando}")
    df = df[df["UF"] == "SP"]
    return pd.DataFrame({
        "cod_ibge": pd.to_numeric(df["cod_IBGE"]).astype(int),
        **{coluna: pd.to_numeric(df[codigo], errors="coerce") for codigo, coluna in codigos.items()},
    })


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    agua = _planilha(baixar("sinisa", "SINISA_Resultados_Ref2024.zip", URL_AGUA, forcar), "AGUA_Indicadores_Base Municipal", INDICADORES_AGUA)
    esgoto = _planilha(baixar("sinisa", "SINISA_ESGOTO_Planilhas_2024.zip", URL_ESGOTO, forcar), "Indicadores_Base Municipal", INDICADORES_ESGOTO)
    df = agua.merge(esgoto, on="cod_ibge", how="outer")
    con.execute("CREATE OR REPLACE TABLE sinisa AS SELECT * FROM df")
    registrar_coleta(con, "sinisa", "2024")
    print(f"  {len(df)} municípios; com tarifa de água: {df['tarifa_agua_m3'].notna().sum()}, "
          f"de esgoto: {df['tarifa_esgoto_m3'].notna().sum()}")
