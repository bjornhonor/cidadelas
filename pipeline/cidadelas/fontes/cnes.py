"""CNES/DATASUS: estabelecimentos de saúde de SP com coordenadas, leitos, equipamentos, médicos, equipes e serviços.

Fonte: arquivo mensal com a base inteira do CNES (~740 MB, todo o Brasil), da página
https://cnes.datasus.gov.br/pages/downloads/arquivosBaseDados.jsp. Para atualizar, troque COMPETENCIA.
"""

import zipfile

import duckdb

from ..db import registrar_coleta
from ..download import baixar
from ..paths import RAW

COMPETENCIA = "202608"
URL = f"https://cnes.datasus.gov.br/EstatisticasServlet?path=BASE_DE_DADOS_CNES_{COMPETENCIA}.ZIP"
TABELAS = [
    "tbEstabelecimento", "rlEstabComplementar", "tbLeito", "rlEstabEquipamento",
    "tbCargaHorariaSus", "rlEstabAtendPrestConv", "tbEquipe", "rlEstabServClass",
]

# CO_UNIDADE começa com o código de 6 dígitos do município; 35 = SP
FILTRO_SP = "CO_UNIDADE LIKE '35%'"


def _ler(tabela: str) -> str:
    caminho = RAW / "cnes" / COMPETENCIA / f"{tabela}{COMPETENCIA}.csv"
    return f"read_csv('{caminho.as_posix()}', delim=';', quote='\"', all_varchar=true, encoding='latin-1', header=true)"


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    zip_path = baixar("cnes", f"BASE_DE_DADOS_CNES_{COMPETENCIA}.ZIP", URL, forcar)
    pasta = RAW / "cnes" / COMPETENCIA
    with zipfile.ZipFile(zip_path) as z:
        for tabela in TABELAS:
            nome = f"{tabela}{COMPETENCIA}.csv"
            if forcar or not (pasta / nome).exists():
                print(f"  extraindo {nome}")
                z.extract(nome, pasta)

    # O código de 6 dígitos do CNES é o de 7 do IBGE sem o dígito verificador
    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_unidades AS
        SELECT e.CO_UNIDADE AS co_unidade, e.CO_CNES AS cnes, m.cod_ibge,
               coalesce(nullif(e.NO_FANTASIA, ''), e.NO_RAZAO_SOCIAL) AS nome,
               e.TP_UNIDADE AS tipo_unidade, e.CO_TURNO_ATENDIMENTO AS turno,
               try_cast(replace(e.NU_LATITUDE, ',', '.') AS DOUBLE) AS lat,
               try_cast(replace(e.NU_LONGITUDE, ',', '.') AS DOUBLE) AS lon,
               EXISTS (
                   SELECT 1 FROM {_ler('rlEstabAtendPrestConv')} a
                   WHERE a.CO_UNIDADE = e.CO_UNIDADE AND a.CO_ATENDIMENTO_PRESTADO = '04' AND a.CO_CONVENIO = '01'
               ) AS urgencia_sus,
               EXISTS (
                   SELECT 1 FROM {_ler('rlEstabAtendPrestConv')} a
                   WHERE a.CO_UNIDADE = e.CO_UNIDADE AND a.CO_ATENDIMENTO_PRESTADO = '04'
               ) AS urgencia
        FROM {_ler('tbEstabelecimento')} e
        JOIN municipios m ON m.cod_ibge // 10 = try_cast(e.CO_MUNICIPIO_GESTOR AS INTEGER)
        WHERE e.{FILTRO_SP} AND coalesce(e.CO_MOTIVO_DESAB, '') = ''
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_leitos AS
        SELECT r.CO_UNIDADE AS co_unidade, r.CO_LEITO AS co_leito, l.DS_LEITO AS leito,
               trim(r.CO_TIPO_LEITO) AS tp_leito,
               coalesce(try_cast(r.QT_EXIST AS INTEGER), 0) AS qt_exist,
               coalesce(try_cast(r.QT_SUS AS INTEGER), 0) AS qt_sus
        FROM {_ler('rlEstabComplementar')} r
        LEFT JOIN {_ler('tbLeito')} l USING (CO_LEITO)
        WHERE r.{FILTRO_SP}
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_equipamentos AS
        SELECT CO_UNIDADE AS co_unidade, trim(CO_TIPO_EQUIPAMENTO) AS tipo, CO_EQUIPAMENTO AS codigo,
               coalesce(try_cast(QT_EXISTENTE AS INTEGER), 0) AS qt_exist,
               coalesce(try_cast(QT_USO AS INTEGER), 0) AS qt_uso,
               TP_SUS = '1' AS disponivel_sus
        FROM {_ler('rlEstabEquipamento')}
        WHERE {FILTRO_SP}
    """)

    # Médicos (CBO 225xxx) com as horas semanais em cada unidade; atende_sus separa o vínculo SUS do particular
    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_medicos AS
        SELECT CO_UNIDADE AS co_unidade, CO_PROFISSIONAL_SUS AS profissional, CO_CBO AS cbo,
               TP_SUS_NAO_SUS = 'S' AS atende_sus,
               coalesce(try_cast(QT_CARGA_HORARIA_AMBULATORIAL AS INTEGER), 0)
                 + coalesce(try_cast(QT_CARGA_HORARIA_OUTROS AS INTEGER), 0)
                 + coalesce(try_cast(QT_CARGA_HOR_HOSP_SUS AS INTEGER), 0) AS horas_semana,
               coalesce(try_cast(QT_CARGA_HORARIA_AMBULATORIAL AS INTEGER), 0) AS horas_ambulatorio
        FROM {_ler('tbCargaHorariaSus')}
        WHERE {FILTRO_SP} AND CO_CBO LIKE '225%'
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_equipes AS
        SELECT m.cod_ibge, e.TP_EQUIPE AS tp_equipe, count(*) AS equipes
        FROM {_ler('tbEquipe')} e
        JOIN municipios m ON m.cod_ibge // 10 = try_cast(e.CO_MUNICIPIO AS INTEGER)
        WHERE coalesce(e.DT_DESATIVACAO, '') = ''
        GROUP BY ALL
    """)

    # Serviços especializados que a unidade declara (ex.: 116-005 hemodinâmica, 140-005 AVC, 105-001 neurotrauma)
    con.execute(f"""
        CREATE OR REPLACE TABLE cnes_servicos AS
        SELECT CO_UNIDADE AS co_unidade, CO_SERVICO AS servico, CO_CLASSIFICACAO AS classificacao,
               bool_or(CO_AMBULATORIAL_SUS = '1' OR CO_HOSPITALAR_SUS = '1') AS sus,
               bool_or(CO_AMBULATORIAL = '1' OR CO_HOSPITALAR = '1' OR CO_AMBULATORIAL_SUS = '1' OR CO_HOSPITALAR_SUS = '1') AS qualquer
        FROM {_ler('rlEstabServClass')}
        WHERE {FILTRO_SP}
        GROUP BY ALL
    """)

    registrar_coleta(con, "cnes", f"{COMPETENCIA[4:]}/{COMPETENCIA[:4]}")
    for tabela in ["cnes_unidades", "cnes_leitos", "cnes_equipamentos", "cnes_medicos", "cnes_equipes", "cnes_servicos"]:
        print(f"  {tabela}: {con.execute(f'SELECT count(*) FROM {tabela}').fetchone()[0]:,} linhas")
