# Metodologia

Ranking pessoal dos 645 municípios de SP. Pesos em [config/ranking.yaml](../config/ranking.yaml).

## Princípios

- **Nenhuma cidade é excluída do ranking.** Exclusão só por filtro manual no app.
- **Clima, altitude e população são filtros**, não entram na nota.
- **Educação não entra.**
- **O pipeline roda manualmente.** Os dados mudam devagar; cada fonte tem seu comando e seu cache em `data/raw/`.

## Cidades pequenas (ruído estatístico)

273 municípios têm menos de 10 mil habitantes, e 150 têm menos de 5 mil. Nesses lugares, um único evento distorce a taxa.

1. **Janela de 5 anos** (hoje, 2021–2025) somada, em vez de um ano isolado.
2. **Encolhimento bayesiano empírico:** a taxa final é uma média ponderada entre a taxa do município e a do resto da
   sua região imediata do IBGE (53 regiões em SP, sem contar o próprio município). O peso do município cresce com o
   número de casos esperados. Cidade grande fica praticamente com a própria taxa; cidade minúscula fica mais perto da
   regional. Quanto pesa a média regional sai dos dados: mede-se o quanto as taxas variam entre cidades além do que o
   acaso explica (máxima verossimilhança da binomial negativa).

   Peso mediano do dado da própria cidade: 58% no crime letal e 96% no roubo. Em 2026-09 a média regional ainda
   incluía o próprio município, e a variação entre cidades era medida com peso pela população. A cidade-polo
   "concordava" com a média que ela mesma domina, a variação saía 2x menor no crime letal e 5x no roubo, e as
   cidades pequenas eram encolhidas demais. Exemplo: Lavínia, 2 crimes letais em 5 anos (4,0 por 100 mil) numa
   região de ~23, ficava com 15,3, uma taxa que pressupõe ~7 casos. Hoje fica com 12,0. Com a correção, 5,5% das
   cidades com poucos casos ficam fora do intervalo de 95% previsto pelo modelo, perto dos 5% esperados.

Isso não pune cidade pequena, tira a loteria. Sem o ajuste, as 17 cidades sem nenhum crime letal em 5 anos seriam
as mais seguras do estado, e uma de 2 mil habitantes com dois homicídios estaria entre as piores. Cidade média ou
grande segura numa região violenta quase não é afetada. Valinhos, na região de Campinas, tem 32 casos em 5 anos: a
taxa passa de 5,0 para 5,8, ainda abaixo do corte dos 2% melhores, e a nota de crimes letais continua 100.

**Limitação: roubo nas cidades minúsculas.** O roubo cresce com o tamanho da cidade, e a taxa regional é dominada pela
cidade-polo. Ao puxar a cidade pequena para a média da região, o ajuste a puxa um pouco para o roubo da cidade
grande. Somando todos os casos de cada faixa (a taxa real do grupo, sem a sorte de cada cidade) e comparando com a
média das taxas ajustadas:

| Faixa | Crimes letais | Roubo |
|---|---|---|
| < 5 mil | −3% | +18% |
| 5–10 mil | −4% | +5% |
| 10–30 mil | −3% | +1% |
| 30 mil ou mais | ~0% | ~0% |

Nas cidades com menos de 5 mil habitantes, isso tira ~3 pontos da nota de roubo, ~1 da de segurança e menos de 1 da
geral. Elas seguem sendo a faixa com a melhor nota média de segurança (62,6, contra 47,5 nas de mais de 100 mil).

## População flutuante (cidades turísticas)

Crime registrado inclui o que acontece com turistas e veranistas, mas a taxa divide pela população residente. Isso
fazia o litoral parecer muito pior do que é para quem mora lá. O denominador passa a ser a **população média do ano**:

    residentes + domicílios de uso ocasional × moradores por domicílio × fração do ano ocupada

Os domicílios de uso ocasional vêm do Censo 2022 (SIDRA 4711). A fração é 25% (`fracao_ano_uso_ocasional` no config),
uma estimativa que cobre temporada, feriados e fins de semana. O efeito: Bertioga +37%, Ubatuba +29%,
Caraguatatuba +15%, e cerca de 1% em São Paulo e Campinas.

**Limitação:** isso não capta quem se hospeda em hotel ou vem só passar o dia, como os romeiros de Aparecida.

## Nota de 0 a 100

Cada indicador vira uma nota comparando os 645 municípios entre si. Os 2% extremos de cada ponta não esticam a escala.
A escala de cada indicador está no config: `log` (padrão, para taxas que variam em ordens de grandeza), `raiz`
(entre log e linear, para não punir muito um valor pequeno), `linear` (percentuais) ou `absoluta` (o valor já é uma nota 0–100, como o acesso na saúde). A nota do tópico é a média ponderada
dos indicadores, e a nota geral é a média ponderada dos tópicos. Indicadores e tópicos sem dado ficam de fora, e os pesos
dos demais são reescalados. Filtrar não muda a nota de ninguém, só o que aparece. O cálculo fica em `web/src/notas.ts`.

## Segurança

Só crime violento contra a pessoa, em dois indicadores (SSP-SP, ocorrências registradas):

- **Crimes letais (peso 60):** homicídio doloso, tentativa de homicídio, latrocínio e lesão corporal seguida de
  morte. A tentativa é o mesmo ato, e sobreviver depende de sorte e socorro. Ela anda junto com os homicídios
  (correlação 0,84 entre as notas) e mais que dobra os casos, então a taxa de cada cidade depende menos da média
  regional (ver "Cidades pequenas"). Limitação: a mesma agressão pode ser
  registrada como lesão ou como tentativa, e esse critério varia entre delegacias.
- **Roubo (peso 40):** roubo de rua e residência mais roubo de veículo. É o crime violento com mais chance de atingir
  um adulto (capital: ~1.050 por 100 mil por ano; homicídio: ~5) e muda a rotina de quem nunca foi vítima. O roubo de
  veículo anda junto com os outros roubos (correlação 0,85), e a soma dá praticamente a mesma nota (0,99).

**Parcela de fato:** com 60 / 40, a letalidade fica com ~66% da variação da nota e o roubo com ~34% (mesma conta da
natureza). Com 70 / 30, o roubo cairia para 19%, e a capital, que tem pouco homicídio e muito roubo, passaria de
cidades como Sorocaba e Ribeirão Preto.

**O que saiu:**
- **Furto:** crime sem violência.
- **Estupro:** 77% dos registros são de estupro de vulnerável, quase sempre contra criança e dentro da família. Isso
  mede abuso doméstico e taxa de denúncia, não o risco de um adulto. O estupro de adulto é raro demais (~8 por 100 mil
  por ano; 6 casos em 5 anos na cidade mediana) para separar uma cidade da outra.
- **Lesão corporal dolosa:** é em boa parte violência doméstica e briga, depende da taxa de denúncia e não tem
  relação com a violência letal (correlação 0,01). Estupro e lesão são mais altos em cidade pequena e o roubo, em
  cidade grande. Por isso os dois se anulavam e tinham parcela de fato ~0, só embaralhando posições.

## Saúde: emergência grave, internação e especialistas

Pensado para dois adultos com plano de saúde: o que mais pesa é chegar a tempo a um hospital que resolve a emergência
grave; depois, ter vaga para internar; e, para o dia a dia, ter especialistas e exames por perto. Saúde e natureza
consideram o entorno, não só o limite municipal.

- **Rede:** SUS e particulares (`rede: sus_mais_privada`). Com `rede: sus` o cálculo volta a contar só a oferta SUS.
- **Origens:** os 103 mil setores censitários de 2022, agrupados dentro de cada município em até 20 pontos pesados
  pela população (1.616 pontos no estado).
- **Tempo de carro:** motor R5 (via `r5py`) sobre o OpenStreetMap de SP, velocidade de via livre, sem trânsito.
  Unidades de outros estados ficam de fora.
- **Coordenadas corrigidas:** o CNES tem unidades marcadas em outra cidade. Os três maiores hospitais de Sorocaba
  apareciam perto de Alumínio, o HC de Marília perto de Garça e o Hospital da Vila Nova Cachoeirinha em Barueri, o
  que dava os leitos para a cidade errada. Unidade a mais de 8 km de qualquer ponto habitado do próprio município vai
  para o ponto mais populoso dele.

**Emergência grave:** tempo até o hospital 24h mais próximo que resolve cada caso, convertido pela curva de
emergência: até 15 min vale 100, 30 min vale 70, 60 min vale 20 ("hora de ouro") e 90 min ou mais vale 0. A nota do
município é a média pesada pela população dos seus pontos. Não basta qualquer pronto-socorro: metade das cidades tem
um a menos de 15 min, e ele só estabiliza e transfere.

- **Infarto:** hospital com hemodinâmica (cateterismo).
- **AVC:** hospital com tomógrafo e UTI adulto.
- **Trauma grave:** hospital com neurocirurgião e UTI adulto.
- **Pronto-socorro 24h** (hospital, PS, UPA): o primeiro atendimento.

Hospitais particulares quase não declaram no CNES os serviços de AVC e trauma (9 de 305 declaram trauma), por isso o
critério é a estrutura, igual para as duas redes. Quem declara o serviço (116-005, 140-005, 105-001) também conta.

**Internação e consultas (capacidade):** E2SFCA (Luo & Qi, 2009). Cada unidade divide sua oferta pela população que a
alcança em 30 min, com peso por faixa de tempo (0–10 min: 1; 10–20: 0,68; 20–30: 0,22). Cada ponto soma o que
alcança com os mesmos pesos. As unidades entram agrupadas em quadrados de ~100 m (prédios de consultórios).

- **Leitos de UTI adulto.**
- **Leitos de internação**, sem psiquiatria, saúde mental, crônicos, reabilitação e acolhimento noturno. Esses eram
  ~20% dos leitos e punham no topo cidades com hospital psiquiátrico (Jaci, Santa Rita do Passa Quatro, Itapira).
- **Especialistas em consultório:** horas de ambulatório de cardiologia, dermatologia, endocrinologia,
  gastroenterologia, ginecologia, oftalmologia, ortopedia, otorrino, urologia, neurologia, psiquiatria e outras
  especialidades de acompanhamento de adulto, em equivalentes de 40h.
- **Tomógrafo e ressonância.**

**Pesos:** infarto 16, AVC 16, trauma 12, pronto-socorro 12; UTI 10, internação 10; especialistas 16, tomógrafo e
ressonância 8. A parcela de fato fica ~53% emergência, ~23% internação e ~24% consultas e exames. O pronto-socorro tem
parcela pequena (~5%) porque tira 100 em metade das cidades. Antes (só SUS, com UTI, médicos e atenção básica) a
emergência tinha 37%, a internação 61% e a consulta 2%, e só a UTI respondia por 44% da nota.

Efeito das mudanças: Sorocaba foi de 205º para 24º em saúde (coordenadas), Avaré de 485º para 153º, Garça de 11º para
128º e Santa Rita do Passa Quatro de 265º para 438º (leitos psiquiátricos).

**O que saiu:** tempo até UTI (os hospitais de infarto, AVC e trauma já têm UTI, e ele andava junto com os leitos de
UTI, correlação 0,83); médicos em geral (anda junto com os especialistas, 0,82); especialistas de hospital
(cirurgião, intensivista; cobertos pelos critérios de emergência); atenção básica e médico de família (a cobertura de
equipes dava 100 em 63% das cidades e tinha parcela de fato negativa).

**Qualidade do hospital:** não há medida de resultado confiável. A acreditação (ONA, JCI) no CNES é declarada pelo
próprio hospital e muitas são antigas (2014); a mortalidade por hospital, sem ajuste pela gravidade, pune os hospitais
de referência, que recebem os casos mais graves. Por isso a qualidade entra como "resolve o caso grave".

**Limitações:** sem trânsito (a capital parece mais perto do que é); o plano de saúde não cobre todo hospital
particular; oferta não é fila: o CNES diz quantos médicos e leitos existem, não quanto se espera.

## Custo de vida

Peso do tópico reduzido de 20 para 15, porque a moradia é estimada na maioria das cidades.

Um indicador só, a **cesta mensal** em reais: quanto mais barata a cidade, maior a nota. A escala é linear (cada real
a mais tira os mesmos pontos em qualquer faixa), porque a cesta varia cerca de 5x entre as cidades (R$ 1.500 a
R$ 7.600), não em ordens de grandeza como as taxas de crime.

Não há comparação com o salário mínimo: ele é igual em todo o estado, então dividir por ele não muda nenhuma nota.

- **Aluguel:** 100 m² × aluguel do m² da cidade (ver moradia abaixo). É ~90% da cesta.
- **Energia:** 200 kWh (família de 2–3 pessoas) × tarifa residencial B1 da distribuidora do município (ANEEL, sem impostos) × 1,30 de
  ICMS e PIS/COFINS. A distribuidora do município vem dos conjuntos elétricos do IndQual.
- **Água e esgoto:** 10 m³ × tarifa média de água + de esgoto (SINISA 2024). Município sem dado, ou com valor
  implausível (fora de 1/3 a 3x a mediana do estado), fica com a mediana da sua região imediata.
- **Mercado: sem fonte por município.** Uma cesta constante (DIEESE capital) não mudaria o ranking.

**Compra do m²:** aparece no detalhe da cidade, mas não entra na nota. Ela e a cesta saem da mesma estimativa de
moradia (correlação 0,99), então somar as duas só contaria o aluguel duas vezes.

### Moradia

- **FipeZap** (anúncios do ZAP, média móvel de 3 meses) cobre 16 cidades de SP com venda e 11 com aluguel,
  quase todas grandes. Onde existe, é o valor usado.
- **Nas demais, estimativa:** o Censo 2010 (o último com valor de aluguel) dá o aluguel médio, em salários mínimos,
  dos imóveis alugados de 5–6 cômodos de cada município. Cidade com poucos alugados é puxada para a média da região
  (30 domicílios fictícios com o valor regional). Uma regressão log-log calibrada nas 16 cidades do FipeZap
  (r = 0,74) transforma isso em R$/m² de venda hoje. O aluguel do m² é a venda × a rentabilidade mediana do aluguel
  no FipeZap (~0,57% ao mês).
- **Limitações:** as cidades de calibração vão de 0,8 a 1,4 salário mínimo de aluguel em 2010; as pequenas do
  interior descem a 0,2, então lá é extrapolação. Cidade turística de alto padrão sai subestimada (Campos do Jordão
  ~R$ 5 mil/m²), porque o aluguel de 2010 é o do morador. O app mostra quando o valor é estimado.
- **O que não deu:** a API do VivaReal fica atrás da proteção antirrobô da Cloudflare, e o projeto não contorna
  esse tipo de bloqueio. O Censo 2022 não perguntou o valor do aluguel na amostra. O CadÚnico tem a despesa com
  aluguel, mas a base pública é amostral, vai só até 2018 e só cobre famílias de baixa renda.

## Infraestrutura

A ordem segue o dano: desastre mata e tira a casa; saneamento afeta a saúde; apagão longo gera caos; fibra é
conforto; ruas e trânsito só desempatam.

- **Desastres:** pessoas mortas, desabrigadas ou desalojadas por 100 mil habitantes em desastres de chuva, solo e
  vento (grupos hidrológico e meteorológico, mais erosão) de 2011 a 2025, no Atlas Digital de Desastres. Antes era
  a contagem de registros, que media mais o tamanho da cidade e o quanto a prefeitura registra (correlação 0,55
  com a população, contra 0,31 agora): Rio Claro saía a pior do estado com 21 registros e 45 atingidos, e São
  Sebastião, com 59 mortos, saía melhor. Um morto conta como um desalojado; como mortes são raras (~300 em 15 anos
  no estado), pesá-las mais mudaria pouco. Limitação: continua dependendo de a prefeitura registrar no S2iD.
  Mapas de área de risco não servem como indicador: o do Serviço Geológico cobre 126 dos 645 municípios, e o do
  IBGE (BATER) é de 2010 e só cobre as cidades monitoradas pelo Cemaden.

  **Escala de raiz quadrada.** Com log, como no crime, uma enxurrada pequena já derrubava a nota: 0,1% da população
  atingida em 15 anos valia 49, e 171 cidades ficavam abaixo de 50 por eventos pequenos, de novo o ruído do
  registro. Com raiz, 0,1% vale 89, 1% vale 66, 3% vale 42 e ~9% ou mais (Vale do Ribeira, Capivari) vale 0.
- **Saneamento:** média de % com água encanada e % de domicílios com esgoto coletado e tratado (SINISA 2024).
- **Quedas de energia:** DEC, horas sem energia por consumidor por ano (ANEEL, média 2023–2025).
- **Internet de fibra:** acessos residenciais de fibra (Anatel, mês mais recente) por 100 domicílios (ocupados e de
  uso ocasional), limitado a 100.
- **Ruas e trânsito:** um indicador só, a média das notas 0–100 de cada parte (calculadas como as do app, com o
  mesmo corte de 2%). O detalhe da cidade mostra os dois valores originais.
  - *Ruas:* média de 5 percentuais do entorno dos domicílios no Censo 2022 (pavimento, bueiro, iluminação, calçada,
    calçada sem obstáculo). Só setores urbanos foram pesquisados.
  - *Trânsito:* carros e motos (SENATRAN, frota com placa) de quem mora na área urbana, por km de rua urbana
    (OpenStreetMap), em escala log. Rua urbana = via de uso local (primary a residential, sem rodovia expressa,
    serviço ou trilha) cujo ponto do meio cai num setor censitário urbano. A frota é multiplicada pela parcela urbana
    da população, para os carros da zona rural não lotarem as poucas ruas da sede. É um proxy de congestionamento:
    não mede horário de pico nem rodovia de passagem.

  Separado, o trânsito tinha parcela de fato negativa: cidade grande tem rua, saneamento e energia bons e trânsito
  ruim, então ele só embaralhava posições.

**Pesos.** 34 / 21 / 17 / 16 / 11 no config dão parcela de fato ~36 / 27 / 18 / 12 / 8 (mesma conta da natureza).
Com o indicador antigo e peso 30, desastres ficava com 57% e a fibra com 2%.

Por que desastres não passa de ~36%: o indicador é metade sorte. Dividindo o período em 2011–2017 e 2018–2025, as
duas metades mal se repetem (correlação 0,31; confiabilidade dos 15 anos ≈ 0,48 por Spearman-Brown), porque desastre
é raro e um município com risco real pode passar anos sem chuva forte. O DEC, por comparação, repete 0,85–0,90 de um
ano para o outro, e o saneamento é cobertura de rede, que muda devagar. Para estimar o risco real, o peso ótimo de um
indicador é proporcional a importância × confiabilidade. Assim, dar ao risco real de desastre ~50% da importância
do tópico, com os demais perto de 0,9, resulta em ~35% de parcela observada (40% → 26%; 60% → 44%). Misturar a cidade
com a média da região, como na segurança, quase não ajuda (correlação entre metades de 0,31 para 0,35).

## Natureza

Mede o verde de onde as pessoas moram, não o do território inteiro: a capital tem 26% de mata nativa, mas ela
fica no extremo sul, a 40 km de quase todo mundo. Verde e área urbana partem de cada setor censitário habitado
(Censo 2022): calcula-se a % da terra (sem rio, lago e mar) num raio em volta dele, no mapa de 30 m do MapBiomas
(Coleção 10, 2024, resumido numa grade de ~300 m), e a média do município é pesada pela população dos setores.

- **Qualidade do ar:** PM2.5 médio de 2023 a 2025 (SISAM, INPE + Ministério da Saúde: reanálise por satélite e
  modelo, grade de ~12 km, todos os municípios). O valor absoluto é superestimado (capital em 2025: 36 µg/m³ na
  reanálise contra 13 na série calibrada com estações, que só existe para a capital), mas a comparação entre cidades
  vale. Com a grade de 12 km, cidades vizinhas da Grande SP herdam parte da poluição dela.
- **Verde perto de casa (3 km) e na região (10 km):** mata nativa ou plantada (eucalipto, pinus), campo nativo e
  mosaico de usos (sítios e chácaras com mata, roça e pasto misturados). Cana, soja, café e pasto de gado não
  contam: a pergunta é "tem muito verde em volta?", e uma planície de lavoura não é isso.
- **Área urbanizada em volta:** % urbanizada num raio de 3 km de casa ("selva de pedra"). Cidade grande sempre
  perde aqui; cidade pequena, cercada de roça, ganha.
- **Arborização:** índice 0–100 de árvores na face de quadra (Censo 2022): 1–2 árvores vale 1/3, 3–4 vale 2/3, 5+ vale 1.

**Pesos.** Ar pesa mais que verde: PM2.5 tem efeito sobre mortalidade sem nível seguro, e o verde conta pelo
convívio e bem-estar. Área urbana e árvore na rua só desempatam. O peso escrito no config não é o peso de fato: os dois
raios de verde medem quase a mesma coisa (correlação 0,9) e área urbana e árvore na rua andam junto com o ar (0,6 e
0,4), porque as três favorecem cidade pequena. Por isso os pesos foram acertados para que a parcela de cada bloco na
variação da nota de natureza entre os 645 municípios (peso × covariância com a nota ÷ variância da nota) fique em
~50% ar, ~40% verde e ~10% desempate. Com pesos 40 / 23+23 / 7+7, ela fica em 52 / 39 / 9. Mudando indicador ou
escala, vale refazer a conta.

Parques e unidades de conservação saíram: a mata de verdade já entra pelo verde, e a lista de proteção
integral deixava de fora APAs como a Cuesta de Botucatu.

## Distância até o trabalho (fora da nota)

Não é tópico do ranking: serve para filtrar e consultar. No app, o modo **remoto** desliga tudo; no **presencial**,
o local de trabalho (endereço buscado no OpenStreetMap ou clique no mapa) vira um tempo de carro para cada cidade.

- **De onde**: os mesmos pontos de origem da saúde (setores do Censo agrupados em até 20 pontos por município,
  pesados pela população). O tempo da cidade é a média desses pontos pesada pela população: é o tempo de quem mora
  lá, não do centro. O detalhe da cidade mostra também o ponto mais perto e o mais longe.
- **Até onde**: o local marcado é preso ao ponto calculado mais próximo. O trecho entre os dois entra como linha reta
  × 1,3 a 30 km/h (número de bom senso, não medido; costuma dar poucos minutos).
- **Como**: carro, ida de manhã, velocidade de via livre (r5py sobre o OSM). **Sem trânsito**: na hora do rush,
  sobretudo na Grande SP, o tempo real é bem maior. Teto de 3 h.
- **Custo**: a matriz de todos os pares de pontos (~1.600 × 1.600, 1 byte cada) é calculada uma vez no pipeline; o
  app só a baixa quando há local marcado, e trocar o local recalcula na hora, sem servidor.

## Cidade por dentro (Valinhos)

A mesma lógica, mas comparando zonas de uma cidade entre si. Por enquanto só Valinhos. Config em
[config/cidades/valinhos.yaml](../config/cidades/valinhos.yaml); no app, "Ver por dentro" no detalhe da cidade.

**Zonas.** O IBGE não tem bairros para Valinhos (o campo vem vazio nos 233 setores do Censo 2022), e o OpenStreetMap
só tem pontos de bairro, sem contorno. Por isso as zonas são grupos de setores vizinhos: um k-means pesado pela
população dá o centro de cada uma, e a zona com menos gente vai anexando o setor vizinho mais perto do seu centro.
São 11 zonas contínuas, de 10,2 mil a 13,3 mil habitantes. O nome são os dois bairros do OSM mais perto do centro da
zona. A divisão fica em `config/cidades/valinhos_setores.csv` e pode ser editada à mão.

**Nota de 0 a 100 só entre as zonas.** Em cada indicador, a pior zona tira 0, a melhor 100, e as outras ficam no
meio em escala linear, sem o corte de 2% do estado. A exceção é a emergência, que já é uma nota pela curva do estado:
as zonas tiram de 94 a 100, e esticar 2 minutos de diferença até 0–100 daria peso a quase nada. Não há ajuste
para poucos casos: é escolha consciente para o MVP, a ser lapidada.

**Segurança.** Microdados dos BOs da SSP (portal SP Dados Criminais, 2022–2025; o portal começa em 2022). Mesmos
crimes do estado: crimes letais (homicídio doloso, tentativa, latrocínio, lesão seguida de morte) e roubo (outros e
de veículo). Os totais de Valinhos batem com os da série mensal oficial (653 roubos e 27 crimes letais em 4 anos).
A taxa é por 100 mil moradores da zona por ano. Peso 60 roubo / 40 letal: o roubo pesa mais aqui porque o letal tem
de 1 a 4 casos por zona. É escolha, não conta; falta medir a parcela de fato.

Onde cada BO cai:
- **Coordenada do BO** quando existe (52% dos letais, 78% dos roubos).
- **Bairro do BO** quando não: crime em residência vem sem endereço nem coordenada ("vedação da divulgação"), mas com
  o bairro. Cada nome de bairro vai para a zona onde cai a maioria dos BOs com coordenada daquele bairro; nome que
  nunca aparece com coordenada vai pelo ponto do bairro no OSM ou pelo núcleo urbano do Censo. Nome cortado
  ("ESPIRITO SANT") vale se for o começo de um único bairro conhecido. "Zona rural" vai para a zona com mais
  moradores em setor rural.
- **Sem zona:** 3 dos 27 letais (dois sem bairro nem coordenada, um com coordenada a 40 km e bairro fora do mapa) e
  1% dos roubos.

Limitação: o BO é registrado onde o crime aconteceu, não onde a vítima mora. A zona do centro comercial conta o roubo
de quem passa por lá.

**Saúde.** Igual ao estado, mas o tempo de carro sai de cada setor censitário em vez de até 20 pontos por município.
A disputa por cada leito ou médico (quantas pessoas alcançam a unidade) vem do cálculo do estado, que considera a
população de toda a região; só muda de onde se parte.

**Infraestrutura.** Só saneamento: % de domicílios com água da rede geral e % com esgoto na rede geral ou pluvial
(inclui fossa ligada à rede), média dos dois, do Censo 2022 por setor. O SINISA do estado não existe por setor.
Desastres, quedas de energia e fibra só existem por município (ou conjunto elétrico) e ficam de fora.

**Natureza.** Verde a até 1 km (a pé) e a até 3 km (de bicicleta, o "perto de casa" do estado) e área urbanizada a
até 1 km, mesmo cálculo e mesmos pesos do estado. O ar fica de fora: a grade do SISAM tem 12 km, a cidade cabe numa
célula. A arborização do Censo só existe por município.

**Custo:** fora. Não há aluguel público por bairro.

## Fontes

| Fonte | Conteúdo | Comando |
|---|---|---|
| IBGE | municípios, regiões, população e domicílios (Censo 2022), malha | `coletar ibge` |
| SSP-SP | ocorrências criminais por município e ano | `coletar ssp` |
| CNES/DATASUS | estabelecimentos, leitos, equipamentos, médicos, equipes | `coletar cnes` |
| OSM + setores do Censo | tempos de carro até as unidades de saúde | `coletar rotas` |
| OSM + setores do Censo | tempos de carro entre os pontos de origem (distância até o trabalho) | `coletar deslocamento` |
| ANEEL | distribuidora, tarifa residencial, DEC/FEC | `coletar aneel` |
| SINISA | tarifas e atendimento de água e esgoto | `coletar sinisa` |
| Censo 2022 (entorno) | ruas e arborização | `coletar entorno` |
| Atlas Digital de Desastres | desastres registrados 1991–2025 | `coletar desastres` |
| MapBiomas | mapa de cobertura do solo de 30 m (recorte de SP) | `coletar mapbiomas` |
| SISAM/INPE | PM2.5 diário por município | `coletar sisam` |
| Anatel | acessos de banda larga por fibra | `coletar anatel` |
| FipeZap + Censo 2010 | preço do m² (venda e aluguel) e aluguel de 2010 | `coletar fipezap` (o de 2010 vem no `ibge`) |
| OSM + SENATRAN | km de rua urbana e frota de carros e motos | `coletar vias` |
| SSP-SP (SP Dados Criminais) | BOs de crimes letais e roubo com bairro e coordenada, 2022–2025 (cidade por dentro) | `coletar ssp_bo` |
| Censo 2022 por setor | água e esgoto dos domicílios (cidade por dentro) | `coletar censo_setores` |
