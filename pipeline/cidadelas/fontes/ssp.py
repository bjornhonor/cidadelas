"""SSP-SP: ocorrências criminais registradas por município e ano (API do portal "Dados Mensais")."""

import json

import duckdb
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar
from ..nomes import chave_nome

BASE = "https://www.ssp.sp.gov.br/v1"
URL_MUNICIPIOS = f"{BASE}/Municipios/RecuperaMunicipios"
# grupoDelito=6 é o grupo "Criminal"; tipoGrupo precisa do acento, como o site envia
URL_OCORRENCIAS = (
    BASE + "/OcorrenciasMensais/RecuperaDadosMensaisAgrupados"
    "?ano={ano}&grupoDelito=6&tipoGrupo=MUNIC%C3%8DPIO&idGrupo={id_ssp}"
)
ANOS = range(2021, 2026)  # 5 anos completos

# Nomes que a SSP grafa diferente do IBGE, mesmo após normalizar acentos e hífens
SSP_PARA_IBGE = {
    "florinia": "florinea",
    "santarosadoviterbo": "santarosadeviterbo",
    "saoluisdoparaitinga": "saoluizdoparaitinga",
}


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    municipios_ssp = json.loads(baixar("ssp", "municipios.json", URL_MUNICIPIOS, forcar).read_text("utf-8"))["data"]

    ibge = con.execute("SELECT cod_ibge, nome FROM municipios").df()
    ibge["chave"] = ibge["nome"].map(chave_nome)
    ssp = pd.DataFrame(municipios_ssp)[["idMunicipio", "nome"]]
    ssp["chave"] = ssp["nome"].map(chave_nome).replace(SSP_PARA_IBGE)
    de_para = ssp.merge(ibge[["cod_ibge", "chave"]], on="chave", how="outer", indicator=True)
    sem_par = de_para[de_para["_merge"] != "both"]
    if not sem_par.empty:
        raise ValueError(f"Municípios SSP x IBGE sem correspondência:\n{sem_par}")

    linhas = []
    for i, (id_ssp, cod_ibge) in enumerate(zip(de_para["idMunicipio"], de_para["cod_ibge"]), 1):
        for ano in ANOS:
            caminho = baixar(
                "ssp", f"ocorrencias/{int(id_ssp)}_{ano}.json",
                URL_OCORRENCIAS.format(ano=ano, id_ssp=int(id_ssp)),
                forcar, silencioso=True, pausa=0.3,
            )
            for bloco in json.loads(caminho.read_text("utf-8"))["data"]:
                for d in bloco["listaDados"]:
                    linhas.append({
                        "cod_ibge": int(cod_ibge),
                        "ano": bloco["ano"],
                        "id_delito": d["delito"]["idDelito"],
                        "delito": d["delito"]["delito"],
                        "ocorrencias": d["total"],
                        "meses_publicados": d["publicado"],
                    })
        if i % 50 == 0:
            print(f"  {i}/{len(de_para)} municípios")

    df = pd.DataFrame(linhas)
    incompletos = df[df["meses_publicados"] < 12]
    if not incompletos.empty:
        print(f"  aviso: {len(incompletos)} registros com menos de 12 meses publicados")

    con.execute("CREATE OR REPLACE TABLE ssp_ocorrencias AS SELECT * FROM df")
    registrar_coleta(con, "ssp", f"{ANOS.start}-{ANOS.stop - 1}")
    print(f"  {df['cod_ibge'].nunique()} municípios, {df['ano'].nunique()} anos, {df['id_delito'].nunique()} tipos de delito")
