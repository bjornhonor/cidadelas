import yaml

from .paths import CONFIG


def carregar() -> dict:
    return yaml.safe_load(CONFIG.read_text("utf-8"))
