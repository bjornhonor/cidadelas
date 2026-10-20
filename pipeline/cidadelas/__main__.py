"""Uso:
    python -m cidadelas coletar ibge
    python -m cidadelas coletar todas [--forcar]
    python -m cidadelas calcular
    python -m cidadelas status
"""

import argparse
import sys

import pandas as pd

from . import config
from .calculo import custo, infraestrutura, natureza, saude, seguranca
from .db import conectar
from .exportar import exportar
from .fontes import FONTES

# Cada tópico e as tabelas (ou fontes, para as que só guardam arquivo) de que depende;
# tópico sem as fontes coletadas fica de fora do cálculo
CALCULOS = [
    (seguranca, ["ssp_ocorrencias"]),
    (saude, ["cnes_unidades", "rotas_tempos"]),
    (custo, ["aneel_municipios", "aneel_tarifas", "sinisa", "fipezap"]),
    (infraestrutura, ["desastres", "censo_entorno", "vias", "sinisa", "aneel_municipios", "anatel_fibra"]),
    (natureza, ["mapbiomas", "rotas", "sisam_pm25", "censo_entorno"]),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # console do Windows usa cp1252 por padrão
    parser = argparse.ArgumentParser(prog="cidadelas")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_coletar = sub.add_parser("coletar", help="baixa e carrega uma fonte no banco")
    p_coletar.add_argument("fonte", choices=[*FONTES, "todas"])
    p_coletar.add_argument("--forcar", action="store_true", help="ignora o cache e baixa de novo")

    sub.add_parser("calcular", help="calcula os indicadores a partir das fontes coletadas")
    sub.add_parser("status", help="mostra quando cada fonte foi coletada")

    args = parser.parse_args()
    con = conectar()

    if args.comando == "coletar":
        fontes = FONTES if args.fonte == "todas" else {args.fonte: FONTES[args.fonte]}
        for nome, coletar in fontes.items():
            print(f"[{nome}]")
            coletar(con, forcar=args.forcar)
    elif args.comando == "calcular":
        cfg = config.carregar()
        existentes = {t for (t,) in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        existentes |= {f for (f,) in con.execute("SELECT fonte FROM coletas").fetchall()}
        partes = []
        for modulo, tabelas in CALCULOS:
            faltando = set(tabelas) - existentes
            if faltando:
                print(f"  pulando {modulo.__name__.split('.')[-1]}: falta coletar {', '.join(sorted(faltando))}")
                continue
            partes.append(modulo.calcular(con, cfg))
        indicadores = pd.concat(partes, ignore_index=True)
        # Registro explícito: com o mesmo nome da tabela, o DuckDB leria a tabela antiga em vez do DataFrame
        con.register("indicadores_novos", indicadores)
        con.execute("CREATE OR REPLACE TABLE indicadores AS SELECT * FROM indicadores_novos")
        print(indicadores.groupby("topico")["indicador"].nunique().to_string())
        exportar(con, indicadores, cfg)
    elif args.comando == "status":
        for fonte, coletado_em, referencia in con.execute("SELECT * FROM coletas ORDER BY fonte").fetchall():
            print(f"{fonte:12} coletado em {coletado_em}  ({referencia})")

    con.close()


if __name__ == "__main__":
    main()
