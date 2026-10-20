"""IBGE: lista dos 645 municípios, regiões, população do Censo 2022 e malha geográfica."""

import json

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios"
# SIDRA tabela 4709, variável 93: população residente (Censo 2022)
URL_POPULACAO = "https://apisidra.ibge.gov.br/values/t/4709/n6/in%20n3%2035/v/93/p/2022"
# SIDRA tabela 4711: domicílios por espécie. 59998 = particular permanente ocupado; 60003 = uso ocasional (veraneio)
URL_DOMICILIOS = "https://apisidra.ibge.gov.br/values/t/4711/n6/in%20n3%2035/v/617/p/2022/c3/59998,60003"
ESPECIES_DOMICILIO = {"59998": "domicilios_ocupados", "60003": "domicilios_uso_ocasional"}
# SIDRA 3511 (Censo 2010, o último com valor de aluguel): domicílios alugados de 5 e 6 cômodos por faixa de aluguel
# em salários mínimos. Serve para estimar o preço de moradia onde o FipeZap não chega.
FAIXAS_ALUGUEL_SM = {  # ponto médio de cada faixa, em salários mínimos
    "13323": 1 / 16, "13328": 3 / 16, "13329": 3 / 8, "13330": 3 / 4,
    "13331": 1.5, "13332": 2.5, "13333": 4, "13334": 6.5,
}
URL_ALUGUEL_2010 = (
    "https://apisidra.ibge.gov.br/values/t/3511/n6/in%20n3%2035/v/1549/p/2010/c511/"
    + ",".join(FAIXAS_ALUGUEL_SM) + "/c125/0/c137/0/c65/1063,1064/c74/0"
)
URL_MALHA = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/35"
    "?intrarregiao=municipio&formato=application/vnd.geo%2Bjson&qualidade=intermediaria"
)


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    municipios = json.loads(baixar("ibge", "municipios.json", URL_MUNICIPIOS, forcar).read_text("utf-8"))
    df_mun = pd.DataFrame([
        {
            "cod_ibge": m["id"],
            "nome": m["nome"],
            "regiao_imediata_id": m["regiao-imediata"]["id"],
            "regiao_imediata": m["regiao-imediata"]["nome"],
            "regiao_intermediaria_id": m["regiao-imediata"]["regiao-intermediaria"]["id"],
            "regiao_intermediaria": m["regiao-imediata"]["regiao-intermediaria"]["nome"],
        }
        for m in municipios
    ])

    # Primeira linha do SIDRA é o cabeçalho
    populacao = json.loads(baixar("ibge", "populacao_censo2022.json", URL_POPULACAO, forcar).read_text("utf-8"))[1:]
    df_pop = pd.DataFrame([{"cod_ibge": int(p["D1C"]), "populacao": int(p["V"])} for p in populacao])

    domicilios = json.loads(baixar("ibge", "domicilios_censo2022.json", URL_DOMICILIOS, forcar).read_text("utf-8"))[1:]
    df_dom = pd.DataFrame([
        {"cod_ibge": int(d["D1C"]), "especie": ESPECIES_DOMICILIO[d["D4C"]], "valor": int(d["V"])}
        for d in domicilios
    ]).pivot(index="cod_ibge", columns="especie", values="valor").reset_index()

    # A API do IBGE entrega o travessão de alguns nomes de região como "¿"
    for coluna in ["regiao_imediata", "regiao_intermediaria"]:
        df_mun[coluna] = df_mun[coluna].str.replace(" ¿ ", " – ", regex=False)

    df = (
        df_mun.merge(df_pop, on="cod_ibge", how="left", validate="1:1")
        .merge(df_dom, on="cod_ibge", how="left", validate="1:1")
    )
    faltando = df[df[["populacao", *ESPECIES_DOMICILIO.values()]].isna().any(axis=1)]
    if not faltando.empty:
        raise ValueError(f"Municípios sem população ou domicílios: {faltando['nome'].tolist()}")

    # A malha fica em disco para o front e para cálculos espaciais; aqui só conferimos a cobertura
    malha = json.loads(baixar("ibge", "malha_sp.geojson", URL_MALHA, forcar).read_text("utf-8"))
    codigos_malha = {int(f["properties"]["codarea"]) for f in malha["features"]}
    if codigos_malha != set(df["cod_ibge"]):
        raise ValueError("Malha e lista de municípios não batem")

    aluguel = json.loads(baixar("ibge", "aluguel_censo2010.json", URL_ALUGUEL_2010, forcar).read_text("utf-8"))[1:]
    df_alu = pd.DataFrame([
        {"cod_ibge": int(a["D1C"]), "sm": FAIXAS_ALUGUEL_SM[a["D4C"]], "n": pd.to_numeric(a["V"], errors="coerce")}
        for a in aluguel
    ]).fillna({"n": 0})
    df_alu = df_alu.assign(peso=df_alu["n"] * df_alu["sm"]).groupby("cod_ibge").agg(
        alugados_2010=("n", "sum"), soma=("peso", "sum")
    ).reset_index()
    df_alu["aluguel_sm_2010"] = df_alu["soma"] / df_alu["alugados_2010"]
    df = df.merge(df_alu[["cod_ibge", "alugados_2010", "aluguel_sm_2010"]], on="cod_ibge", how="left", validate="1:1")

    con.execute("CREATE OR REPLACE TABLE municipios AS SELECT * FROM df")
    registrar_coleta(con, "ibge", "Censo 2022")
    print(f"  {len(df)} municípios, {df['populacao'].sum():,} habitantes")
