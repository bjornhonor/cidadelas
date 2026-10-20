import re
import unicodedata


def chave_nome(nome: str) -> str:
    """Chave para casar nomes de município entre fontes: sem acento, caixa, hífen ou apóstrofo."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())
