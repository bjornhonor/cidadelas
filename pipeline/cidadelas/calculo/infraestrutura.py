"""Infraestrutura: desastres, saneamento, quedas de energia, internet de fibra e ruas e trânsito."""

import duckdb
import numpy as np
import pandas as pd

# Desastres ligados a chuva, solo e vento (o que a pessoa sente como alagamento, deslizamento, destelhamento)
GRUPOS_DESASTRE = ("Hidrológico", "Meteorológico")
TIPOS_EXTRA = ("Erosão",)  # vem classificado como "Outros"
ANOS_DESASTRES = (2011, 2025)
CORTE = 0.02  # mesmo corte de web/src/notas.ts


def _nota(x: pd.Series, menor_melhor: bool) -> pd.Series:
    """Nota 0–100 como o app calcula: os 2% extremos de cada ponta não esticam a escala."""
    lo, hi = x.quantile(CORTE), x.quantile(1 - CORTE)
    relativo = (x.clip(lo, hi) - lo) / (hi - lo)
    return 100 * (1 - relativo if menor_melhor else relativo)


def calcular(con: duckdb.DuckDBPyConnection, cfg: dict) -> pd.DataFrame:
    partes = []

    # Pessoas mortas, desabrigadas ou desalojadas por 100 mil habitantes no período: mede o risco de quem mora lá.
    # Contar os registros favorecia cidade pequena e quem registra pouco (Rio Claro: 21 registros, 45 atingidos)
    desastres = con.execute(f"""
        SELECT m.cod_ibge, coalesce(sum(d.dh_mortos), 0) AS mortos,
               1e5 * coalesce(sum(d.dh_mortos + d.dh_desabrigados + d.dh_desalojados), 0) / m.populacao AS valor
        FROM municipios m LEFT JOIN desastres d ON d.cod_ibge = m.cod_ibge
            AND year(d.data) BETWEEN {ANOS_DESASTRES[0]} AND {ANOS_DESASTRES[1]}
            AND (d.grupo IN {GRUPOS_DESASTRE} OR d.tipo IN {TIPOS_EXTRA})
        GROUP BY m.cod_ibge, m.populacao ORDER BY m.cod_ibge
    """).df()
    partes.append(desastres.assign(
        indicador="desastres",
        unidade=f"mortos, desabrigados e desalojados por 100 mil hab. em chuva, solo e vento, "
                f"{ANOS_DESASTRES[0]}–{ANOS_DESASTRES[1]}",
    ))

    saneamento = con.execute("""
        -- Média do que existe: sem o dado de esgoto tratado, vale só a água (e vice-versa)
        SELECT cod_ibge, list_avg(list_filter([atendimento_agua_pct, esgoto_tratado_pct], x -> x IS NOT NULL)) AS valor
        FROM sinisa WHERE atendimento_agua_pct IS NOT NULL OR esgoto_tratado_pct IS NOT NULL
    """).df()
    partes.append(saneamento.assign(
        indicador="saneamento", unidade="média de % com água encanada e % de domicílios com esgoto coletado e tratado",
    ))

    energia = con.execute("SELECT cod_ibge, dec_horas AS valor FROM aneel_municipios WHERE dec_horas IS NOT NULL").df()
    partes.append(energia.assign(indicador="quedas_energia", unidade="horas sem energia por consumidor por ano (DEC)"))

    # Casas de veraneio também assinam internet, então entram no denominador. Ainda pode passar de 100%
    # (pequenas empresas registradas como pessoa física): corta em 100
    fibra = con.execute("""
        SELECT m.cod_ibge,
               least(100, 100 * coalesce(f.acessos_fibra, 0) / (m.domicilios_ocupados + m.domicilios_uso_ocasional)) AS valor
        FROM municipios m LEFT JOIN anatel_fibra f USING (cod_ibge)
    """).df()
    partes.append(fibra.assign(indicador="internet_fibra", unidade="acessos residenciais de fibra por 100 domicílios"))

    # Ruas e trânsito: um indicador só, média das duas notas. Separado, o trânsito tinha parcela de fato negativa
    # (cidade grande tem rua boa e trânsito ruim) e só embaralhava posições
    ruas = con.execute("""
        SELECT cod_ibge,
               100 * (pavimentada + bueiro + iluminacao + calcada + calcada_sem_obstaculo) / (5 * total) AS ruas_pct
        FROM censo_entorno WHERE total > 0
    """).df()
    # Trânsito: quantos carros e motos de quem mora na área urbana disputam cada km de rua urbana
    # (proxy de congestionamento; a frota é proporcional à parcela urbana da população)
    transito = con.execute("""
        SELECT cod_ibge, veiculos * fracao_urbana / km_rua_urbana AS veiculos_km
        FROM vias WHERE km_rua_urbana > 0 AND veiculos > 0
    """).df()
    rt = ruas.merge(transito, on="cod_ibge")
    rt["valor"] = (_nota(rt["ruas_pct"], False) + _nota(np.log1p(rt["veiculos_km"]), True)) / 2
    partes.append(rt.assign(
        indicador="ruas_transito",
        unidade="nota 0–100: média de ruas completas (pavimento, bueiro, luz, calçada) e de poucos carros por km de rua",
    ))

    return pd.concat(partes, ignore_index=True).assign(topico="infraestrutura")
