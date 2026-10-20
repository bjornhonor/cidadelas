export const TOPICOS: Record<string, string> = {
  seguranca: 'Segurança',
  saude: 'Saúde',
  custo: 'Custo de vida',
  infraestrutura: 'Infraestrutura',
  natureza: 'Natureza',
}

// Cabeçalho das colunas do ranking, onde o espaço é curto
export const TOPICOS_CURTOS: Record<string, string> = {
  seguranca: 'Seg.',
  saude: 'Saúde',
  custo: 'Custo',
  infraestrutura: 'Infra.',
  natureza: 'Nat.',
}

const INDICADORES: Record<string, string> = {
  crimes_letais: 'Crimes letais',
  roubo: 'Roubo',
  tempo_infarto: 'Tempo até hospital de infarto',
  tempo_avc: 'Tempo até hospital de AVC',
  tempo_trauma: 'Tempo até hospital de trauma',
  tempo_pronto_socorro: 'Tempo até pronto-socorro',
  leitos_uti: 'Leitos de UTI',
  leitos_agudos: 'Leitos de internação',
  especialistas: 'Especialistas em consultório',
  equipamentos: 'Tomógrafo e ressonância',
  cesta_mensal: 'Cesta mensal (R$)',
  desastres: 'Desastres',
  saneamento: 'Saneamento',
  quedas_energia: 'Quedas de energia',
  internet_fibra: 'Internet de fibra',
  ruas_transito: 'Ruas e trânsito',
  ar_pm25: 'Qualidade do ar (PM2.5)',
  verde_perto: 'Verde perto de casa',
  verde_regiao: 'Verde na região',
  area_urbana: 'Área urbanizada em volta',
  arborizacao: 'Arborização',
}

export const rotuloIndicador = (id: string) => INDICADORES[id] ?? id.replaceAll('_', ' ')

export const formatarNumero = (n: number, casas = 0) =>
  n.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
