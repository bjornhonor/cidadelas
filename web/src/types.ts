// Formato de public/data/cidadelas.json, gerado por `python -m cidadelas calcular`

export type Sentido = 'maior_melhor' | 'menor_melhor'

export type Escala = 'log' | 'raiz' | 'linear' | 'absoluta'

export interface ConfigIndicador {
  peso: number
  sentido: Sentido
  escala?: Escala // padrão: log
  fonte?: string
}

export interface ConfigTopico {
  peso: number
  indicadores: Record<string, ConfigIndicador>
  [parametro: string]: unknown
}

export interface Config {
  topicos: Record<string, ConfigTopico>
  filtros_apenas: string[]
  corte?: number // fração dos extremos que não estica a escala; padrão 0,02 (dentro da cidade é 0)
}

export interface ValorIndicador {
  valor: number // o que entra na nota (em segurança, já ajustado para cidade pequena)
  // Campos que só alguns tópicos têm
  bruto?: number // segurança: taxa só com os dados do município
  eventos?: number // segurança: casos em 5 anos
  peso_local?: number // segurança: 0..1, quanto do valor vem do próprio município
  minutos?: number // saúde: tempo médio de carro até a unidade mais próxima
  compra_m2?: number // custo: R$ por m² para comprar (só consulta, fora da nota)
  estimado?: number // custo: 1 quando a moradia é estimada (cidade fora do FipeZap)
  mortos?: number // desastres: mortos no período
  ruas_pct?: number // ruas e trânsito: % médio de ruas completas
  veiculos_km?: number // ruas e trânsito: carros e motos por km de rua urbana
}

export interface Municipio {
  cod: number
  nome: string
  populacao: number
  regiao_imediata: string
  regiao_intermediaria: string
  bairros?: string[] // só nas zonas de uma cidade: bairros do OpenStreetMap dentro da zona
  indicadores: Record<string, ValorIndicador>
}

export interface Dados {
  gerado_em: string
  coletas: { fonte: string; coletado_em: string; referencia: string }[]
  config: Config
  unidades: Record<string, string>
  // Só nos dados de uma cidade por dentro (public/data/cidades/): aí cada "município" é uma zona
  cidade?: { cod: number; nome: string; anos_crime: number }
  municipios: Municipio[]
}

// public/data/cidades/index.json: cidades que têm a visão por dentro
export interface CidadeDetalhada {
  cod: number
  slug: string
  nome: string
}

export interface Pesos {
  topicos: Record<string, number>
  indicadores: Record<string, Record<string, number>>
  desligados: string[] // tópicos fora da nota geral; o peso deles continua guardado para quando voltarem
}

export interface Notas {
  geral: number | null
  topicos: Record<string, number | null>
  indicadores: Record<string, number>
}
