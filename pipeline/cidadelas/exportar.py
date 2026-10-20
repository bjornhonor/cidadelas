"""Gera os arquivos que o app web lê: web/public/data/cidadelas.json, malha_sp.geojson e, se coletado, deslocamento."""

import json
from datetime import date

import duckdb
import numpy as np
import pandas as pd

from .paths import RAIZ, RAW

DESTINO = RAIZ / "web" / "public" / "data"


def exportar(con: duckdb.DuckDBPyConnection, indicadores: pd.DataFrame, cfg: dict) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    municipios = con.execute("""
        SELECT cod_ibge, nome, populacao, regiao_imediata, regiao_intermediaria
        FROM municipios ORDER BY nome
    """).df()

    # Campos opcionais: cada tópico tem os seus (segurança tem casos e peso local; saúde tem minutos...)
    extras = {
        "valor_bruto": "bruto", "eventos": "eventos", "peso_local": "peso_local", "minutos": "minutos",
        "compra_m2": "compra_m2", "estimado": "estimado", "mortos": "mortos", "ruas_pct": "ruas_pct",
        "veiculos_km": "veiculos_km",
    }
    por_municipio: dict[int, dict] = {}
    for linha in indicadores.to_dict("records"):
        if pd.isna(linha["valor"]):  # sem dado: o app trata como indicador ausente para esse município
            continue
        valor = {"valor": round(float(linha["valor"]), 3)}
        for coluna, chave in extras.items():
            if coluna in linha and pd.notna(linha[coluna]):
                valor[chave] = round(float(linha[coluna]), 3)
        por_municipio.setdefault(linha["cod_ibge"], {})[linha["indicador"]] = valor

    unidades = indicadores.drop_duplicates("indicador").set_index("indicador")["unidade"].to_dict()
    dados = {
        "gerado_em": date.today().isoformat(),
        "coletas": [
            {"fonte": f, "coletado_em": c.isoformat(), "referencia": r}
            for f, c, r in con.execute("SELECT * FROM coletas ORDER BY fonte").fetchall()
        ],
        "config": cfg,
        "unidades": unidades,
        "municipios": [
            {
                "cod": int(m.cod_ibge),
                "nome": m.nome,
                "populacao": int(m.populacao),
                "regiao_imediata": m.regiao_imediata,
                "regiao_intermediaria": m.regiao_intermediaria,
                "indicadores": por_municipio.get(m.cod_ibge, {}),
            }
            for m in municipios.itertuples()
        ],
    }
    # allow_nan=False: NaN no JSON quebra o app em silêncio, melhor falhar aqui
    (DESTINO / "cidadelas.json").write_text(json.dumps(dados, ensure_ascii=False, allow_nan=False), "utf-8")

    # Malha só com o código do município, que é o que o mapa precisa para ligar aos dados
    malha = json.loads((RAW / "ibge" / "malha_sp.geojson").read_text("utf-8"))
    for f in malha["features"]:
        f["properties"] = {"cod": int(f["properties"]["codarea"])}
    (DESTINO / "malha_sp.geojson").write_text(json.dumps(malha, separators=(",", ":")), "utf-8")
    _exportar_deslocamento(con)
    print(f"  exportado para {DESTINO.relative_to(RAIZ)}")


SEM_ROTA = 255  # no binário: sem rota de carro em até 3 h


def _exportar_deslocamento(con: duckdb.DuckDBPyConnection) -> None:
    """Matriz de minutos entre os pontos de origem: 1 byte por par, linha = de onde sai, coluna = aonde chega.

    O app só baixa quando há local de trabalho marcado. Os pontos vão num JSON à parte, na mesma ordem da matriz.
    """
    if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'deslocamento_tempos'").fetchone()[0]:
        return
    pontos = con.execute("SELECT id, cod_ibge, pop, lat, lon FROM rotas_origens ORDER BY id").df()
    assert (pontos["id"] == np.arange(len(pontos))).all(), "ids dos pontos precisam ser 0..n-1"
    tempos = con.execute("SELECT origem, destino, minutos FROM deslocamento_tempos").df()
    matriz = np.full((len(pontos), len(pontos)), SEM_ROTA, dtype=np.uint8)
    matriz[tempos["origem"], tempos["destino"]] = np.minimum(tempos["minutos"].round(), SEM_ROTA - 1)
    (DESTINO / "deslocamento.bin").write_bytes(matriz.tobytes())
    (DESTINO / "deslocamento.json").write_text(json.dumps({
        "sem_rota": SEM_ROTA,
        "pontos": [
            [int(p.cod_ibge), int(p.pop), round(float(p.lat), 5), round(float(p.lon), 5)] for p in pontos.itertuples()
        ],
    }, separators=(",", ":")), "utf-8")
    print(f"  deslocamento: {len(pontos)} pontos, {matriz.nbytes / 1e6:.1f} MB")
