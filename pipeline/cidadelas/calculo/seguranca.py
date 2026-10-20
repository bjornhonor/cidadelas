"""Indicadores de segurança: taxas por 100 mil habitantes/ano, janela de 5 anos, com encolhimento."""

import duckdb
import pandas as pd

from .encolhimento import encolher

# Indicador do config/ranking.yaml -> ids de delito da SSP somados
DELITOS = {
    # homicídio doloso, tentativa de homicídio, latrocínio, lesão corporal seguida de morte
    "crimes_letais": [38, 42, 52, 130],
    # roubo - outros + roubo de veículo (sem banco e carga, que não afetam o morador)
    "roubo": [133, 37],
}


def calcular(con: duckdb.DuckDBPyConnection, cfg: dict) -> pd.DataFrame:
    fracao_ocasional = cfg["topicos"]["seguranca"]["fracao_ano_uso_ocasional"]
    anos = con.execute("SELECT count(DISTINCT ano) FROM ssp_ocorrencias").fetchone()[0]
    municipios = con.execute("""
        SELECT cod_ibge, regiao_imediata_id,
               -- população média ao longo do ano: residentes + ocupantes de casas de veraneio
               populacao + domicilios_uso_ocasional * (populacao / domicilios_ocupados) * ? AS populacao_media
        FROM municipios ORDER BY cod_ibge
    """, [fracao_ocasional]).df()
    exposicao = municipios["populacao_media"] * anos  # pessoas-ano

    resultados = []
    for indicador, ids in DELITOS.items():
        eventos = con.execute(f"""
            SELECT m.cod_ibge, coalesce(sum(o.ocorrencias), 0) AS eventos
            FROM municipios m
            LEFT JOIN ssp_ocorrencias o ON o.cod_ibge = m.cod_ibge AND o.id_delito IN ({",".join(map(str, ids))})
            GROUP BY m.cod_ibge ORDER BY m.cod_ibge
        """).df()["eventos"]
        taxas = encolher(eventos, exposicao, municipios["regiao_imediata_id"])
        resultados.append(pd.DataFrame({
            "cod_ibge": municipios["cod_ibge"],
            "topico": "seguranca",
            "indicador": indicador,
            "eventos": eventos,
            "valor_bruto": taxas["taxa_bruta"] * 100_000,
            "valor": taxas["taxa_ajustada"] * 100_000,
            "peso_local": taxas["peso_local"],
            "unidade": "por 100 mil hab/ano",
        }))
    return pd.concat(resultados, ignore_index=True)
