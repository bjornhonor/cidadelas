"""ANEEL: tarifa residencial de energia e continuidade do fornecimento (DEC/FEC) por município.

A ANEEL não publica "distribuidora do município" diretamente. O caminho é:
município → conjuntos elétricos (IndQual Município) → distribuidora de cada conjunto (arquivo de continuidade).
Quando um município tem mais de uma distribuidora, vale a que atende mais consumidores nos seus conjuntos.
"""

import duckdb

from ..db import registrar_coleta
from ..download import baixar

BASE = "https://dadosabertos.aneel.gov.br/dataset"
URL_MUNICIPIOS = f"{BASE}/db9c9f60-b3b5-4504-9dfe-2637922d53ce/resource/3f841488-80a8-42f2-a6ca-e0c593b228de/download/indqual-municipio.csv"
URL_CONTINUIDADE = f"{BASE}/d5f0712e-62f6-4736-8dff-9991f10758a7/resource/d7f70fb1-725c-4748-afeb-65c6a78df550/download/indicadores-continuidade-coletivos-2020-2029.parquet"
URL_TARIFAS = f"{BASE}/5a583f3e-1646-4f67-bf0f-69db4203e89e/resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4/download/tarifas-homologadas-distribuidoras-energia-eletrica.csv"

ANOS_CONTINUIDADE = (2023, 2025)  # 3 anos completos
# Concessões incorporadas que ainda aparecem com o nome antigo nos conjuntos elétricos
AGENTE_TARIFA = {"CPFL JAGUARI": "CPFL Santa Cruz"}


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    municipios = baixar("aneel", "indqual-municipio.csv", URL_MUNICIPIOS, forcar)
    continuidade = baixar("aneel", "continuidade-2020-2029.parquet", URL_CONTINUIDADE, forcar)
    tarifas = baixar("aneel", "tarifas-homologadas.csv", URL_TARIFAS, forcar)

    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW aneel_conj_mun AS
        SELECT DISTINCT CodMunicipio::INTEGER AS cod_ibge, IdeConjUnidConsumidoras AS conjunto
        FROM read_csv('{municipios.as_posix()}', delim=';', all_varchar=true, encoding='latin-1', header=true)
        WHERE SigUF = 'SP'
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW aneel_cont AS
        SELECT IdeConjUndConsumidoras::VARCHAR AS conjunto, trim(SigAgente) AS agente, SigIndicador AS indicador,
               AnoIndice AS ano, NumPeriodoIndice AS mes, VlrIndiceEnviado AS valor
        FROM '{continuidade.as_posix()}'
        WHERE AnoIndice BETWEEN {ANOS_CONTINUIDADE[0]} AND {ANOS_CONTINUIDADE[1]}
    """)

    # DEC (horas sem energia por consumidor no ano) e FEC (vezes), apurados; média dos conjuntos do município
    # pesada pelo número de consumidores de cada conjunto
    con.execute("""
        CREATE OR REPLACE TABLE aneel_municipios AS
        WITH consumidores AS (
            SELECT conjunto, agente, avg(valor) AS consumidores
            FROM aneel_cont WHERE indicador = 'NumCon' GROUP BY ALL
        ),
        anual AS (
            SELECT conjunto, ano, indicador, sum(valor) AS valor
            FROM aneel_cont WHERE indicador IN ('DEC', 'FEC') GROUP BY ALL
        ),
        por_conjunto AS (
            SELECT conjunto,
                   avg(valor) FILTER (WHERE indicador = 'DEC') AS dec_horas,
                   avg(valor) FILTER (WHERE indicador = 'FEC') AS fec_vezes
            FROM anual GROUP BY ALL
        ),
        mun AS (
            SELECT m.cod_ibge, c.agente, c.consumidores, p.dec_horas, p.fec_vezes
            FROM aneel_conj_mun m
            JOIN consumidores c ON c.conjunto = m.conjunto
            LEFT JOIN por_conjunto p ON p.conjunto = m.conjunto
        )
        SELECT cod_ibge,
               arg_max(agente, consumidores) AS distribuidora,
               sum(dec_horas * consumidores) / sum(consumidores) FILTER (WHERE dec_horas IS NOT NULL) AS dec_horas,
               sum(fec_vezes * consumidores) / sum(consumidores) FILTER (WHERE fec_vezes IS NOT NULL) AS fec_vezes
        FROM mun GROUP BY cod_ibge
    """)

    # Tarifa residencial convencional B1 (TUSD + TE, R$/MWh, sem impostos), a vigência mais recente de cada distribuidora
    con.execute(f"""
        CREATE OR REPLACE TABLE aneel_tarifas AS
        SELECT SigAgente AS agente,
               arg_max(DatInicioVigencia, DatInicioVigencia) AS inicio_vigencia,
               arg_max((replace(VlrTUSD, ',', '.')::DOUBLE + replace(VlrTE, ',', '.')::DOUBLE) / 1000, DatInicioVigencia) AS reais_kwh
        FROM read_csv('{tarifas.as_posix()}', delim=';', all_varchar=true)
        WHERE DscSubGrupo = 'B1' AND DscModalidadeTarifaria = 'Convencional' AND DscSubClasse = 'Residencial'
          AND DscDetalhe = 'Não se aplica' AND DscBaseTarifaria = 'Tarifa de Aplicação'
          AND DatInicioVigencia <= current_date::VARCHAR
        GROUP BY SigAgente
    """)
    for antigo, novo in AGENTE_TARIFA.items():
        con.execute("UPDATE aneel_municipios SET distribuidora = ? WHERE distribuidora = ?", [novo, antigo])

    sem_tarifa = con.execute("""
        SELECT DISTINCT distribuidora FROM aneel_municipios
        WHERE distribuidora NOT IN (SELECT agente FROM aneel_tarifas)
    """).fetchall()
    if sem_tarifa:
        raise ValueError(f"Distribuidoras sem tarifa: {sem_tarifa}")
    faltando = con.execute("SELECT count(*) FROM municipios WHERE cod_ibge NOT IN (SELECT cod_ibge FROM aneel_municipios)").fetchone()[0]
    if faltando:
        raise ValueError(f"{faltando} municípios sem distribuidora")

    registrar_coleta(con, "aneel", f"tarifas vigentes; DEC/FEC {ANOS_CONTINUIDADE[0]}-{ANOS_CONTINUIDADE[1]}")
    print(con.execute("""
        SELECT count(*) AS municipios, count(DISTINCT distribuidora) AS distribuidoras,
               round(avg(dec_horas), 1) AS dec_medio_horas
        FROM aneel_municipios
    """).df().to_string(index=False))
