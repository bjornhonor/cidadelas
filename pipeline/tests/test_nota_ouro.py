"""A nota 0–100 do pipeline (ruas e trânsito) tem de ser a mesma do app: os dois testam contra testes/notas_ouro.json."""

import json

import numpy as np
import pandas as pd
import pytest

from cidadelas.calculo.infraestrutura import CORTE, _nota
from cidadelas.paths import RAIZ

OURO = json.loads((RAIZ / "testes" / "notas_ouro.json").read_text("utf-8"))


@pytest.mark.parametrize("caso", OURO["casos"], ids=lambda c: c["nome"])
def test_nota_igual_a_do_app(caso):
    assert caso["corte"] == CORTE
    x = pd.Series(caso["valores"], dtype=float)
    if caso["escala"] == "log":
        x = np.log1p(x)  # o app aplica o log antes de normalizar, como infraestrutura.py faz no trânsito
    elif caso["escala"] != "linear":
        pytest.skip(f"escala {caso['escala']} não existe no pipeline")
    nota = _nota(x, caso["sentido"] == "menor_melhor")
    np.testing.assert_allclose(nota, caso["esperado"], atol=1e-5)
