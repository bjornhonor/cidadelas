"""FipeZap: preço médio do m² residencial (venda e aluguel), último mês, nas cidades de SP que o índice cobre.

São 16 cidades com venda e 11 com aluguel. Médias móveis de 3 meses de preços de anúncio (ZAP).
"""

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar
from ..nomes import chave_nome

URL = "https://downloads.fipe.org.br/indices/fipezap/fipezap-serieshistoricas.xlsx"


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    planilhas = pd.read_excel(baixar("fipezap", "fipezap-serieshistoricas.xlsx", URL, forcar), sheet_name=None, header=None)
    municipios = con.execute("SELECT cod_ibge, nome FROM municipios").df()
    por_chave = dict(zip(municipios["nome"].map(chave_nome), municipios["cod_ibge"]))

    linhas = []
    for nome, d in planilhas.items():
        # Cada planilha é uma cidade; as de outros estados não casam com nenhum município de SP.
        # Se um dia o FipeZap incluir uma homônima de fora (não há hoje), ela entraria aqui por engano.
        cod = por_chave.get(chave_nome(nome))
        if cod is None:
            continue
        # As colunas de "Preço médio (R$/m²)" residenciais são a 1ª (venda) e a 2ª (aluguel)
        precos = [c for c in d.columns if isinstance(d.iloc[2, c], str) and d.iloc[2, c].startswith("Preço médio")][:2]
        serie = d.iloc[4:, [1, *precos]].set_axis(["mes", "venda", "aluguel"], axis=1)
        serie = serie[pd.to_datetime(serie["mes"], errors="coerce").notna()]
        for coluna in ["venda", "aluguel"]:
            valores = pd.to_numeric(serie[coluna], errors="coerce")
            if valores.notna().any():
                linhas.append({"cod_ibge": cod, "negocio": coluna, "reais_m2": valores.dropna().iloc[-1],
                               "mes": pd.to_datetime(serie.loc[valores.dropna().index[-1], "mes"]).strftime("%Y-%m")})

    df = pd.DataFrame(linhas).pivot(index="cod_ibge", columns="negocio", values="reais_m2").reset_index()
    df.columns = ["cod_ibge", *[f"{c}_m2" for c in df.columns[1:]]]
    con.execute("CREATE OR REPLACE TABLE fipezap AS SELECT * FROM df")
    mes = max(l["mes"] for l in linhas)
    registrar_coleta(con, "fipezap", mes)
    print(f"  {df['venda_m2'].notna().sum()} cidades com venda, {df['aluguel_m2'].notna().sum()} com aluguel ({mes})")
