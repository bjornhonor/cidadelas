"""Custo de vida: cesta mensal de serviços essenciais em reais; o preço do m² para comprar vai junto, só para consulta.

Cesta = aluguel de um imóvel de referência + energia + água/esgoto. Mercado ainda não tem fonte por município.

Moradia: o FipeZap cobre só 16 cidades de SP (11 com aluguel). Nas demais, o preço de venda do m² é estimado pelo
aluguel médio de imóveis de 5–6 cômodos do Censo 2010 (o último com valor de aluguel), numa regressão log-log
calibrada nas cidades do FipeZap. O aluguel do m² é o preço de venda × a rentabilidade mediana do aluguel no FipeZap.
As cidades do FipeZap vão do aluguel 2010 de 0,8 a 1,4 salário mínimo; as pequenas do interior descem a 0,2, então
lá é extrapolação: vale para comparar cidades, não como preço exato.
"""

import duckdb
import numpy as np
import pandas as pd

# Cidade com poucos domicílios alugados em 2010 tem média ruidosa: puxa para a região como se tivesse
# esse número de domicílios extras com o valor regional
PSEUDO_DOMICILIOS = 30


def _moradia(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        SELECT m.cod_ibge, m.regiao_imediata_id, m.alugados_2010, m.aluguel_sm_2010, f.venda_m2, f.aluguel_m2
        FROM municipios m LEFT JOIN fipezap f USING (cod_ibge)
    """).df()
    soma = (df["alugados_2010"] * df["aluguel_sm_2010"]).groupby(df["regiao_imediata_id"]).transform("sum")
    regional = soma / df.groupby("regiao_imediata_id")["alugados_2010"].transform("sum")
    n = df["alugados_2010"].fillna(0)
    df["aluguel_2010"] = (n * df["aluguel_sm_2010"].fillna(0) + PSEUDO_DOMICILIOS * regional) / (n + PSEUDO_DOMICILIOS)

    calibracao = df.dropna(subset=["venda_m2"])
    inclinacao, intercepto = np.polyfit(np.log(calibracao["aluguel_2010"]), np.log(calibracao["venda_m2"]), 1)
    estimado_venda = np.exp(intercepto + inclinacao * np.log(df["aluguel_2010"]))
    ambos = df.dropna(subset=["venda_m2", "aluguel_m2"])
    rentabilidade = (ambos["aluguel_m2"] / ambos["venda_m2"]).median()

    df["estimado"] = df["venda_m2"].isna().astype(float)
    df["venda_m2"] = df["venda_m2"].fillna(estimado_venda)
    df["aluguel_m2"] = df["aluguel_m2"].fillna(df["venda_m2"] * rentabilidade)
    print(f"  moradia: venda = e^{intercepto:.2f} × aluguel2010^{inclinacao:.2f} (calibrado em {len(calibracao)} cidades); "
          f"aluguel = {100 * rentabilidade:.2f}% da venda ao mês")
    return df[["cod_ibge", "venda_m2", "aluguel_m2", "estimado"]]


def calcular(con: duckdb.DuckDBPyConnection, cfg: dict) -> pd.DataFrame:
    c = cfg["topicos"]["custo"]
    df = con.execute("""
        SELECT m.cod_ibge, m.regiao_imediata_id, t.reais_kwh, s.tarifa_agua_m3, s.tarifa_esgoto_m3
        FROM municipios m
        JOIN aneel_municipios a USING (cod_ibge)
        JOIN aneel_tarifas t ON t.agente = a.distribuidora
        LEFT JOIN sinisa s USING (cod_ibge)
    """).df().merge(_moradia(con), on="cod_ibge", validate="1:1")

    # Município sem tarifa no SINISA, ou com valor implausível (menos de 1/3 ou mais de 3x a mediana do estado,
    # como os R$ 79/m³ de Reginópolis), fica com a mediana da sua região imediata
    for coluna in ["tarifa_agua_m3", "tarifa_esgoto_m3"]:
        mediana = df[coluna].median()
        df.loc[(df[coluna] < mediana / 3) | (df[coluna] > mediana * 3), coluna] = None
        mediana_regional = df.groupby("regiao_imediata_id")[coluna].transform("median")
        df[coluna] = df[coluna].fillna(mediana_regional).fillna(df[coluna].median())

    aluguel = c["area_referencia_m2"] * df["aluguel_m2"]
    energia = c["consumo_kwh"] * df["reais_kwh"] * c["fator_impostos_energia"]
    agua = c["consumo_agua_m3"] * (df["tarifa_agua_m3"] + df["tarifa_esgoto_m3"])
    return pd.DataFrame({
        "cod_ibge": df["cod_ibge"], "topico": "custo", "indicador": "cesta_mensal",
        "valor": aluguel + energia + agua, "compra_m2": df["venda_m2"], "estimado": df["estimado"],
        "unidade": f"R$ por mês (aluguel de {c['area_referencia_m2']} m² + luz {c['consumo_kwh']} kWh "
                   f"+ água e esgoto {c['consumo_agua_m3']} m³)",
    })
