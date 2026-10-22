"""Encolhimento: com dados simulados de variação conhecida, o modelo precisa achar a variação e encolher do jeito certo."""

import numpy as np
import pandas as pd

from cidadelas.calculo.encolhimento import encolher


def _simular(phi: float, semente: int = 0, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    regiao = np.repeat(np.arange(20), n // 20)
    exposicao = np.exp(rng.uniform(np.log(2e4), np.log(5e7), n))  # de cidade minúscula a capital, em pessoas-ano
    media = 1e-4
    taxa = rng.gamma(1 / phi, media * phi, n)  # média `media`, variância phi × média²
    eventos = rng.poisson(taxa * exposicao)
    return pd.DataFrame({"y": eventos, "E": exposicao, "regiao": regiao, "taxa": taxa})


def test_acha_a_variacao_real_entre_municipios():
    for phi in (0.1, 0.5):
        d = _simular(phi)
        estimado = encolher(d["y"], d["E"], d["regiao"])["phi"].iloc[0]
        assert phi / 2 < estimado < phi * 2, (phi, estimado)


def test_cidade_grande_fica_com_a_propria_taxa_e_a_pequena_vai_para_a_regiao():
    d = _simular(0.5)
    r = encolher(d["y"], d["E"], d["regiao"])
    grande, pequena = d["E"].idxmax(), d["E"].idxmin()
    assert r.loc[grande, "peso_local"] > 0.95
    assert r.loc[pequena, "peso_local"] < 0.5
    # a taxa ajustada fica entre a bruta e a regional
    for i in (grande, pequena):
        lo, hi = sorted([r.loc[i, "taxa_bruta"], r.loc[i, "taxa_regional"]])
        assert lo - 1e-12 <= r.loc[i, "taxa_ajustada"] <= hi + 1e-12


def test_encolher_erra_menos_que_a_taxa_bruta():
    d = _simular(0.5, semente=1)
    r = encolher(d["y"], d["E"], d["regiao"])
    erro = lambda estimativa: np.mean((estimativa - d["taxa"]) ** 2)  # noqa: E731
    assert erro(r["taxa_ajustada"]) < erro(r["taxa_bruta"])


def test_cidade_sem_nenhum_caso_nao_fica_com_taxa_zero():
    d = _simular(0.5)
    sem_caso = d.index[(d["y"] == 0)]
    assert len(sem_caso), "a simulação precisa ter cidade sem caso"
    r = encolher(d["y"], d["E"], d["regiao"])
    assert (r.loc[sem_caso, "taxa_ajustada"] > 0).all()


def test_media_regional_nao_inclui_o_proprio_municipio():
    d = pd.DataFrame({"y": [10, 0, 0], "E": [1e4, 1e4, 1e4], "regiao": [1, 1, 1]})
    r = encolher(d["y"], d["E"], d["regiao"])
    assert np.isclose(r.loc[1, "taxa_regional"], 10 / 2e4)  # o resto da região: só o município 0 teve casos
    assert np.isclose(r.loc[0, "taxa_regional"], 10 / 3e4)  # o resto não teve caso nenhum: vale a região inteira
