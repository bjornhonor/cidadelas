from . import anatel, aneel, cnes, deslocamento, desastres, entorno, fipezap, ibge, mapbiomas, rotas, sinisa, sisam, ssp, vias

# Ordem importa: outras fontes dependem da tabela de municípios do IBGE, e rotas depende do CNES
FONTES = {
    "ibge": ibge.coletar,
    "ssp": ssp.coletar,
    "cnes": cnes.coletar,
    "rotas": rotas.coletar,
    "aneel": aneel.coletar,
    "sinisa": sinisa.coletar,
    "entorno": entorno.coletar,
    "desastres": desastres.coletar,
    "mapbiomas": mapbiomas.coletar,
    "sisam": sisam.coletar,
    "anatel": anatel.coletar,
    "fipezap": fipezap.coletar,
    "vias": vias.coletar,  # depois de rotas, que baixa o OSM e os setores
    "deslocamento": deslocamento.coletar,  # depois de rotas, que cria os pontos de origem
}
