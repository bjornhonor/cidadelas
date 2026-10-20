"""Download com cache em data/raw: só baixa de novo com forcar=True."""

import time
from functools import cache
from pathlib import Path

import httpx

from .paths import RAW

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


@cache
def _cliente() -> httpx.Client:
    # Um cliente só: criar o contexto TLS a cada requisição custa ~2 s no Windows
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True)


def baixar(fonte: str, nome: str, url: str, forcar: bool = False, silencioso: bool = False, pausa: float = 0) -> Path:
    """pausa: segundos de espera após um download real, para não martelar o servidor."""
    destino = RAW / fonte / nome
    if destino.exists() and not forcar:
        if not silencioso:
            print(f"  cache: {destino.relative_to(RAW)}")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not silencioso:
        print(f"  baixando: {url}")
    # Grava em partes num .part e só renomeia no fim: arquivos grandes não passam pela memória
    # e um download interrompido não vira cache corrompido
    parcial = destino.with_name(destino.name + ".part")
    with _cliente().stream("GET", url) as resposta:
        resposta.raise_for_status()
        with parcial.open("wb") as arquivo:
            for bloco in resposta.iter_bytes(1 << 20):
                arquivo.write(bloco)
    parcial.replace(destino)
    time.sleep(pausa)
    return destino
