// Tempo de carro até o trabalho, a partir de public/data/deslocamento.{json,bin} (`coletar deslocamento`)

export interface LocalTrabalho {
  lat: number
  lon: number
  rotulo: string
}

/** O local fica guardado mesmo no modo remoto, para voltar ao presencial sem buscar de novo. */
export interface Trabalho {
  modo: 'remoto' | 'presencial'
  local: LocalTrabalho | null
}

export interface Deslocamento {
  pontos: { cod: number; pop: number; lat: number; lon: number }[]
  matriz: Uint8Array // n × n minutos, linha = de onde sai, coluna = aonde chega
  semRota: number
}

export interface TempoTrabalho {
  minutos: number // média da cidade, pesada pela população de cada ponto
  min: number // ponto da cidade mais perto do trabalho
  max: number
}

/** Tempo máximo da matriz: acima disso o pipeline não roteia. */
export const TETO_MINUTOS = 180

// Trecho entre o local marcado e o ponto calculado mais próximo: linha reta × 1,3 (ruas não são retas) a 30 km/h
// (média urbana). Número de bom senso, não medido: em geral é um trecho de 1 a 3 km, alguns minutos.
const DESVIO_RUAS = 1.3
const KM_POR_MINUTO = 30 / 60

const CHAVE = 'cidadelas:trabalho'

export function lerTrabalho(): Trabalho {
  try {
    const salvo = JSON.parse(localStorage.getItem(CHAVE) ?? 'null') as Trabalho | null
    const local = salvo?.local && Number.isFinite(salvo.local.lat) && Number.isFinite(salvo.local.lon) ? salvo.local : null
    if (salvo) return { modo: salvo.modo === 'presencial' ? 'presencial' : 'remoto', local }
  } catch {
    // armazenamento bloqueado ou valor corrompido: começa como remoto
  }
  return { modo: 'remoto', local: null }
}

export function salvarTrabalho(t: Trabalho) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(t))
  } catch {
    // navegação privada: vale só nesta sessão
  }
}

export async function carregarDeslocamento(): Promise<Deslocamento> {
  const [info, bin] = await Promise.all([
    fetch('/data/deslocamento.json').then((r) => {
      if (!r.ok) throw new Error('sem deslocamento.json')
      return r.json() as Promise<{ sem_rota: number; pontos: [number, number, number, number][] }>
    }),
    fetch('/data/deslocamento.bin').then((r) => {
      if (!r.ok) throw new Error('sem deslocamento.bin')
      return r.arrayBuffer()
    }),
  ])
  const pontos = info.pontos.map(([cod, pop, lat, lon]) => ({ cod, pop, lat, lon }))
  const matriz = new Uint8Array(bin)
  if (matriz.length !== pontos.length ** 2) throw new Error('matriz de deslocamento com tamanho errado')
  return { pontos, matriz, semRota: info.sem_rota }
}

export function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2
    + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(a))
}

/**
 * Minutos de carro (sem trânsito) de cada cidade até o trabalho: ida de manhã, de cada ponto onde a população mora
 * até o ponto calculado mais perto do trabalho, mais o trecho final estimado. Ponto sem rota em 3 h conta como 3 h.
 * Também devolve a distância em linha reta até esse ponto, para avisar quando o local marcado está longe de tudo.
 */
export function temposAteTrabalho(d: Deslocamento, lat: number, lon: number) {
  let alvo = 0
  let kmAlvo = Infinity
  d.pontos.forEach((p, i) => {
    const km = distanciaKm(lat, lon, p.lat, p.lon)
    if (km < kmAlvo) {
      alvo = i
      kmAlvo = km
    }
  })
  const trechoFinal = (kmAlvo * DESVIO_RUAS) / KM_POR_MINUTO
  const n = d.pontos.length

  const somas = new Map<number, { soma: number; pop: number; min: number; max: number }>()
  d.pontos.forEach((p, i) => {
    const bruto = d.matriz[i * n + alvo]
    const minutos = Math.min(bruto === d.semRota ? TETO_MINUTOS : bruto, TETO_MINUTOS) + trechoFinal
    const s = somas.get(p.cod) ?? { soma: 0, pop: 0, min: Infinity, max: 0 }
    s.soma += minutos * p.pop
    s.pop += p.pop
    s.min = Math.min(s.min, minutos)
    s.max = Math.max(s.max, minutos)
    somas.set(p.cod, s)
  })
  const tempos = new Map<number, TempoTrabalho>(
    [...somas].map(([cod, s]) => [cod, { minutos: s.soma / s.pop, min: s.min, max: s.max }]),
  )
  return { tempos, kmAtePonto: kmAlvo }
}

export function formatarMinutos(m: number): string {
  if (m >= TETO_MINUTOS) return '3 h+'
  if (m < 60) return `${Math.round(m)} min`
  const h = Math.floor(m / 60)
  const resto = Math.round(m - h * 60)
  return resto === 60 ? `${h + 1} h` : `${h} h${resto ? ` ${String(resto).padStart(2, '0')}` : ''}`
}
