from cidadelas.nomes import chave_nome


def test_ignora_acento_caixa_hifen_e_apostrofo():
    assert chave_nome("São Luiz do Paraitinga") == "saoluizdoparaitinga"
    assert chave_nome("Estrela d'Oeste") == chave_nome("ESTRELA D OESTE") == "estreladoeste"
    assert chave_nome("Embu-Guaçu") == chave_nome("Embu Guacu")


def test_nomes_diferentes_continuam_diferentes():
    assert chave_nome("Santa Rosa de Viterbo") != chave_nome("Santa Rosa do Viterbo")
