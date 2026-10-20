# Cidadelas

Ranking pessoal dos municípios de São Paulo: segurança, saúde, custo de vida, infraestrutura e natureza.
Critérios e decisões em [docs/metodologia.md](docs/metodologia.md); pesos em [config/ranking.yaml](config/ranking.yaml).

## Pipeline de dados

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e pipeline
.venv/Scripts/python -m cidadelas coletar todas   # ou: coletar ibge | coletar ssp
.venv/Scripts/python -m cidadelas status          # quando cada fonte foi coletada
```

Os arquivos baixados ficam em `data/raw/`, e rodar de novo reaproveita o cache. Use `--forcar` para baixar tudo outra vez.
O banco local fica em `data/cidadelas.duckdb`. O `calcular` também grava `web/public/data/`, que é o que o app lê.

## App

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

No painel "Trabalho", escolha remoto ou presencial. No presencial, busque o endereço (vai para o Nominatim, do
OpenStreetMap) ou marque no mapa: o app mostra o tempo de carro até cada cidade e filtra por tempo máximo. Precisa de
`coletar deslocamento` (alguns minutos, depois de `coletar rotas`) seguido de `calcular`.

As notas e os pesos são calculados no navegador, então mexer num peso reordena o ranking na hora. Os pesos que você
ajusta ficam salvos no navegador. O botão "restaurar" volta aos valores de `config/ranking.yaml`.
