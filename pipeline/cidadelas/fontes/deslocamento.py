"""Tempo de carro entre os pontos onde a população mora, para o app medir a distância até o trabalho.

- Pontos: os mesmos de `rotas` (setores censitários agrupados em até 20 pontos por município, pesados pela
  população). O app prende o local de trabalho ao ponto mais próximo e lê daqui o tempo até cada ponto das outras
  cidades; o tempo da cidade é a média pesada pela população dos pontos dela.
- Rotas: r5py sobre o recorte de SP do OpenStreetMap, velocidade de via livre (sem trânsito), como em `rotas`.
- Teto de 3 h: para ir ao trabalho, mais que isso não interessa, e o custo do roteamento cresce com o teto.
- Retomável: cada lote pronto vai para data/raw/deslocamento/<pontos>/. Dá para interromper (Ctrl+C ou fechar) e
  rodar de novo: os lotes já gravados são pulados. Se `rotas` mudar os pontos, a pasta muda e o cálculo recomeça.

Depende de `coletar rotas` (pontos de origem e mapa viário). É demorado (horas): são 2,6 milhões de pares.
"""

import hashlib
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import duckdb
import geopandas as gpd
import pandas as pd

from ..db import registrar_coleta
from ..download import baixar
from ..paths import RAW
from .rotas import ORIGENS_POR_LOTE, THREADS, URL_OSM

TEMPO_MAXIMO = timedelta(hours=3)


def _pasta_lotes(pontos: pd.DataFrame):
    # Os lotes só valem para os mesmos pontos: a pasta leva uma impressão digital deles
    assinatura = hashlib.sha1(pontos[["id", "lat", "lon"]].round(6).to_csv(index=False).encode()).hexdigest()[:12]
    return RAW / "deslocamento" / f"{len(pontos)}_{assinatura}"


def _gravar(tempos: pd.DataFrame, destino) -> None:
    # Grava num .part e renomeia: lote interrompido no meio da escrita não vira lote "pronto"
    parcial = destino.with_name(destino.name + ".part")
    with duckdb.connect() as tmp:
        tmp.register("tempos", tempos)
        tmp.execute(f"COPY tempos TO '{parcial.as_posix()}' (FORMAT parquet)")
    parcial.replace(destino)


def coletar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> None:
    pontos = con.execute("SELECT id, lat, lon FROM rotas_origens ORDER BY id").df()
    pasta = _pasta_lotes(pontos)
    if forcar and pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    todos = gpd.GeoDataFrame(pontos[["id"]], geometry=gpd.points_from_xy(pontos["lon"], pontos["lat"]), crs="EPSG:4326")
    lotes = {
        pasta / f"lote_{i // ORIGENS_POR_LOTE:04d}.parquet": todos.iloc[i:i + ORIGENS_POR_LOTE]
        for i in range(0, len(todos), ORIGENS_POR_LOTE)
    }
    faltando = {arquivo: lote for arquivo, lote in lotes.items() if not arquivo.exists()}
    print(f"  {len(pontos)} pontos, {len(pontos) ** 2:,} pares; {len(lotes) - len(faltando)}/{len(lotes)} lotes já prontos")

    if faltando:
        import r5py  # sobe uma JVM ao ser importado: só quando há o que rotear

        osm = baixar("osm", "sao-paulo-latest.osm.pbf", URL_OSM, forcar)
        print("  montando a rede viária (demora alguns minutos)")
        rede = r5py.TransportNetwork(osm)
        feitos = len(lotes) - len(faltando)

        def rotear(item):
            nonlocal feitos
            arquivo, lote = item
            m = r5py.TravelTimeMatrix(
                rede, origins=lote, destinations=todos,
                transport_modes=[r5py.TransportMode.CAR],
                departure=datetime(2026, 9, 1, 10, 0),  # só importa para transporte público
                max_time=TEMPO_MAXIMO,
            )
            tempos = pd.DataFrame(m).dropna(subset=["travel_time"])
            _gravar(tempos[["from_id", "to_id", "travel_time"]], arquivo)
            feitos += 1
            print(f"    {feitos}/{len(lotes)} lotes ({datetime.now():%H:%M})", flush=True)

        print("  calculando tempos de carro (pode interromper: rodar de novo continua daqui)")
        with ThreadPoolExecutor(THREADS) as executor:
            list(executor.map(rotear, faltando.items()))

    con.execute(f"""
        CREATE OR REPLACE TABLE deslocamento_tempos AS
        SELECT from_id AS origem, to_id AS destino, travel_time AS minutos
        FROM read_parquet('{(pasta / "lote_*.parquet").as_posix()}')
    """)
    registrar_coleta(con, "deslocamento", "OSM SP, carro sem trânsito, até 3 h")
    total = con.execute("SELECT count(*) FROM deslocamento_tempos").fetchone()[0]
    print(f"  {total:,} pares com rota em até 3 h")
