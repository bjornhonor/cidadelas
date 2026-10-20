"""Indicadores de saúde: chegar a tempo a quem resolve a emergência grave, ter vaga e ter especialista e exame perto.

Rede: `sus` conta só a oferta SUS; `sus_mais_privada` conta tudo o que está no CNES (quem tem plano de saúde).

Acesso: para cada ponto de origem, o tempo até a unidade mais próxima de cada tipo vira uma nota pela curva de
emergência (15 min = 100, 30 = 70, 60 = 20, 90+ = 0). A nota do município é a média pesada pela população.

Capacidade (E2SFCA, Luo & Qi 2009): cada unidade divide sua oferta pela população que a alcança dentro do raio,
com peso que cai com o tempo (0–10 min: 1; 10–20: 0,68; 20–30: 0,22). Cada ponto soma as ofertas que alcança, com
os mesmos pesos. Assim, uma cidade pequena ao lado de um polo herda parte dos leitos dele, e o polo não conta os
leitos como se fossem só dos seus moradores. As unidades entram agrupadas nas células de ~100 m das rotas.
"""

import duckdb
import numpy as np
import pandas as pd

CURVA_EMERGENCIA = ([0, 15, 30, 60, 90], [100, 100, 70, 20, 0])

UTI_ADULTO = ("74", "75", "76", "85", "86", "51")  # UTI adulto I/II/III, coronariana II/III, UTI adulto SRAG
TIPOS_PRONTO_SOCORRO = ("05", "07", "15", "20", "21", "73")  # hospitais, unidade mista, PS, pronto atendimento/UPA
HOSPITAIS = ("05", "07")  # hospital geral e especializado
# Leitos que não atendem problema agudo: psiquiatria, saúde mental, crônicos, acolhimento noturno, reabilitação,
# pneumologia sanitária (tuberculose de longa permanência). São ~20% dos leitos e se concentram em cidades pequenas
LEITOS_LONGA_PERMANENCIA = ("47", "73", "87", "34", "84", "48", "49")
NEUROCIRURGIAO = "225260"
# Especialistas que um adulto procura para acompanhamento e exames de rotina (horas de ambulatório)
ESPECIALISTAS_CONSULTA = (
    "225109",  # nefrologista
    "225112",  # neurologista
    "225115",  # angiologista
    "225120",  # cardiologista
    "225121",  # oncologista clínico
    "225127",  # pneumologista
    "225133",  # psiquiatra
    "225135",  # dermatologista
    "225136",  # reumatologista
    "225155",  # endocrinologista
    "225165",  # gastroenterologista
    "225180",  # geriatra
    "225203",  # cirurgião vascular
    "225250",  # ginecologista e obstetra
    "225255",  # mastologista
    "225265",  # oftalmologista
    "225270",  # ortopedista e traumatologista
    "225275",  # otorrinolaringologista
    "225280",  # coloproctologista
    "225285",  # urologista
)


def _peso_distancia(minutos: pd.Series, raio: float) -> np.ndarray:
    faixa = minutos / raio
    return np.select([faixa <= 1 / 3, faixa <= 2 / 3, faixa <= 1], [1.0, 0.68, 0.22], 0.0)


def _por_municipio(origens: pd.DataFrame, valor_origem: pd.Series) -> pd.Series:
    v = origens[["cod_ibge", "pop"]].assign(v=valor_origem.reindex(origens["id"]).fillna(0).to_numpy())
    return v.groupby("cod_ibge").apply(lambda g: np.average(g["v"], weights=g["pop"]), include_groups=False)


def _acesso(origens, tempos, unidades) -> tuple[pd.Series, pd.Series]:
    t = tempos[tempos["destino"].isin(unidades)].groupby("origem")["minutos"].min()
    t = t.reindex(origens["id"])  # sem unidade dentro do limite da busca (90 min): nota 0, tempo conta como 90
    nota = pd.Series(np.interp(t.fillna(999), *CURVA_EMERGENCIA), index=origens["id"])
    return _por_municipio(origens, nota), _por_municipio(origens, t.fillna(CURVA_EMERGENCIA[0][-1]))


def razao_oferta(origens, tempos, oferta: pd.Series, raio: float) -> pd.Series:
    """Primeiro passo do E2SFCA: oferta de cada célula por pessoa que a alcança no raio (com peso pelo tempo)."""
    t = tempos[(tempos["minutos"] <= raio) & tempos["destino"].isin(oferta.index)].copy()
    t["w"] = _peso_distancia(t["minutos"], raio)
    t["pop"] = t["origem"].map(origens.set_index("id")["pop"])
    demanda = (t["pop"] * t["w"]).groupby(t["destino"]).sum()
    return oferta / demanda


def acessivel(tempos, razao: pd.Series, raio: float) -> pd.Series:
    """Segundo passo: cada origem soma a razão das células que alcança, com o mesmo peso pelo tempo."""
    t = tempos[(tempos["minutos"] <= raio) & tempos["destino"].isin(razao.index)].copy()
    t["r"] = t["destino"].map(razao) * _peso_distancia(t["minutos"], raio)
    return t.groupby("origem")["r"].sum()


def _capacidade(origens, tempos, oferta: pd.Series, raio: float, por: int) -> pd.Series:
    return _por_municipio(origens, acessivel(tempos, razao_oferta(origens, tempos, oferta, raio), raio)) * por


def conjuntos(con: duckdb.DuckDBPyConnection, cfg: dict) -> tuple[dict, dict]:
    """Unidades que contam para cada indicador de acesso e oferta por célula de cada indicador de capacidade."""
    saude = cfg["topicos"]["saude"]
    so_sus = {"sus": True, "sus_mais_privada": False}[saude["rede"]]

    # Filtros de rede: só SUS, ou tudo o que existe
    leito = "qt_sus" if so_sus else "qt_exist"
    equip = "disponivel_sus AND qt_exist > 0" if so_sus else "qt_exist > 0"
    medico = "atende_sus" if so_sus else "true"
    servico = "sus" if so_sus else "qualquer"
    urgencia = "urgencia_sus" if so_sus else "urgencia"
    rede = "SUS" if so_sus else "SUS e particulares"

    def unidades(sql: str) -> set:
        return set(con.execute(sql).df().iloc[:, 0])

    def oferta(sql: str) -> pd.Series:
        df = con.execute(f"""
            SELECT d.celula, sum(o.v) FROM ({sql}) o(co_unidade, v)
            JOIN rotas_destinos d USING (co_unidade) GROUP BY 1
        """).df()
        return df.set_index("celula").iloc[:, 0].astype(float)

    # Hospital 24h que resolve o caso grave. Particulares quase não declaram o serviço no CNES, então vale também a
    # estrutura: hemodinâmica para o infarto, tomógrafo + UTI para o AVC, neurocirurgião + UTI para o trauma
    hospital = f"SELECT co_unidade FROM cnes_unidades WHERE tipo_unidade IN {HOSPITAIS} AND turno = '06'"
    uti = f"SELECT co_unidade FROM cnes_leitos WHERE co_leito IN {UTI_ADULTO} GROUP BY 1 HAVING sum({leito}) > 0"
    def declara(servico_classe: str) -> str:
        s, c = servico_classe.split("-")
        return f"SELECT co_unidade FROM cnes_servicos WHERE servico = '{s}' AND classificacao = '{c}' AND {servico}"
    def equipamento(codigo: str) -> str:
        return f"SELECT co_unidade FROM cnes_equipamentos WHERE tipo = '1' AND codigo = '{codigo}' AND {equip}"
    neurocirurgiao = f"SELECT co_unidade FROM cnes_medicos WHERE cbo = '{NEUROCIRURGIAO}' AND {medico}"

    acessos = {
        "tempo_infarto": unidades(f"""{hospital} AND (co_unidade IN ({equipamento('10')})
                                                      OR co_unidade IN ({declara('116-005')}))"""),
        "tempo_avc": unidades(f"""{hospital} AND ((co_unidade IN ({equipamento('11')}) AND co_unidade IN ({uti}))
                                                  OR co_unidade IN ({declara('140-005')}))"""),
        "tempo_trauma": unidades(f"""{hospital} AND ((co_unidade IN ({neurocirurgiao}) AND co_unidade IN ({uti}))
                                                     OR co_unidade IN ({declara('105-001')}))"""),
        "tempo_pronto_socorro": unidades(f"""
            SELECT co_unidade FROM cnes_unidades
            WHERE tipo_unidade IN {TIPOS_PRONTO_SOCORRO} AND turno = '06' AND {urgencia}"""),
    }
    capacidades = {
        # indicador: (oferta por célula, multiplicador, unidade)
        "leitos_uti": (oferta(f"SELECT co_unidade, sum({leito}) FROM cnes_leitos WHERE co_leito IN {UTI_ADULTO} GROUP BY 1"),
                       100_000, f"leitos de UTI adulto ({rede}) por 100 mil hab."),
        "leitos_agudos": (oferta(f"""
            SELECT co_unidade, sum({leito}) FROM cnes_leitos
            WHERE tp_leito <> '3' AND co_leito NOT IN {LEITOS_LONGA_PERMANENCIA} GROUP BY 1"""),
            1_000, f"leitos de internação ({rede}, sem psiquiatria e longa permanência) por mil hab."),
        "especialistas": (oferta(f"""
            SELECT co_unidade, sum(horas_ambulatorio) / 40 FROM cnes_medicos
            WHERE {medico} AND cbo IN {ESPECIALISTAS_CONSULTA} GROUP BY 1"""),
            100_000, f"especialistas em consultório ({rede}, 40h) por 100 mil hab."),
        "equipamentos": (oferta(f"""
            SELECT co_unidade, sum(qt_exist) FROM cnes_equipamentos
            WHERE tipo = '1' AND codigo IN ('11', '12') AND {equip} GROUP BY 1"""),
            100_000, f"tomógrafos e ressonâncias ({rede}) por 100 mil hab."),
    }
    return acessos, capacidades


def calcular(con: duckdb.DuckDBPyConnection, cfg: dict) -> pd.DataFrame:
    raio = cfg["topicos"]["saude"]["raio_capacidade_min"]
    origens = con.execute("SELECT * FROM rotas_origens").df()
    tempos = con.execute("SELECT * FROM rotas_tempos").df()
    acessos, capacidades = conjuntos(con, cfg)

    linhas = []
    for indicador, conjunto in acessos.items():
        nota, minutos = _acesso(origens, tempos, conjunto)
        linhas.append(pd.DataFrame({
            "cod_ibge": nota.index, "indicador": indicador, "valor": nota.to_numpy(),
            "minutos": minutos.to_numpy(), "unidade": "nota de acesso (0 a 100)",
        }))
    for indicador, (s, por, unidade) in capacidades.items():
        valor = _capacidade(origens, tempos, s, raio, por)
        linhas.append(pd.DataFrame({"cod_ibge": valor.index, "indicador": indicador, "valor": valor.to_numpy(), "unidade": unidade}))

    df = pd.concat(linhas, ignore_index=True).assign(topico="saude")
    # Todo município precisa aparecer em todos os indicadores (quem não alcança nada fica com 0)
    completo = pd.MultiIndex.from_product(
        [con.execute("SELECT cod_ibge FROM municipios").df()["cod_ibge"], df["indicador"].unique()],
        names=["cod_ibge", "indicador"],
    )
    faltando = completo.difference(df.set_index(["cod_ibge", "indicador"]).index)
    if len(faltando):
        raise ValueError(f"{len(faltando)} pares município-indicador sem valor, ex.: {list(faltando[:3])}")
    return df
