"""Encolhimento bayesiano empírico de taxas (modelo Poisson-Gama).

Cada município i tem y_i eventos numa exposição E_i (pessoas-ano). A taxa bruta r_i = y_i / E_i
é ruidosa quando E_i é pequena. Supomos que a taxa verdadeira vem de uma Gama com média m_i
(taxa do resto da região imediata, sem o próprio município) e variância phi * m_i². Então a estimativa a posteriori é

    taxa_ajustada = w_i * r_i + (1 - w_i) * m_i,   com   w_i = phi*m_i*E_i / (phi*m_i*E_i + 1)

ou seja, o peso do dado local cresce com o número esperado de eventos (m_i * E_i).

phi (a variação relativa real entre municípios) é estimado por máxima verossimilhança da binomial negativa.
A média regional exclui o próprio município: com ele dentro, a cidade-polo "concorda" com a média que ela mesma
domina, e phi saía subestimado (2x no crime letal, 5x no roubo), encolhendo demais as cidades pequenas.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import gammaln


def _log_verossimilhanca(phi: float, y: np.ndarray, mu: np.ndarray) -> float:
    """Binomial negativa (Poisson com taxa Gama) de média mu e variância mu + phi*mu²."""
    k = 1 / phi
    return (gammaln(y + k) - gammaln(k) - gammaln(y + 1)
            + k * np.log(k / (k + mu)) + y * np.log(mu / (k + mu))).sum()


def encolher(eventos: pd.Series, exposicao: pd.Series, regiao: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": eventos, "E": exposicao, "regiao": regiao})
    soma = df.groupby("regiao")[["y", "E"]].transform("sum")
    # média do resto da região; se o resto não teve nenhum evento, usa a da região inteira
    m = ((soma["y"] - df["y"]) / (soma["E"] - df["E"])).where(lambda s: s > 0, soma["y"] / soma["E"])
    r = df["y"] / df["E"]

    validos = m > 0
    phi = 0.0
    if validos.any():
        y, mu = df["y"][validos].to_numpy(), (m * df["E"])[validos].to_numpy()
        phi = minimize_scalar(lambda p: -_log_verossimilhanca(p, y, mu), bounds=(1e-4, 5), method="bounded").x

    esperado = phi * m * df["E"]
    w = esperado / (esperado + 1)
    return pd.DataFrame({
        "taxa_bruta": r,
        "taxa_regional": m,
        "peso_local": w,
        "taxa_ajustada": w * r + (1 - w) * m,
    }).assign(phi=phi)
