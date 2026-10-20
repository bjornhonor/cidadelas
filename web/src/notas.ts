import type { Config, Municipio, Notas, Pesos } from './types'

const CORTE = 0.02 // os 2% extremos de cada ponta não esticam a escala

function quantil(ordenados: number[], q: number): number {
  const pos = (ordenados.length - 1) * q
  const base = Math.floor(pos)
  const resto = pos - base
  return ordenados[base] + (ordenados[base + 1] !== undefined ? resto * (ordenados[base + 1] - ordenados[base]) : 0)
}

/**
 * Converte cada indicador numa nota 0..100 comparando os 645 municípios entre si, com corte nos extremos.
 * Escala logarítmica por padrão (taxas de crime variam em ordens de grandeza); "raiz" fica entre log e linear;
 * "absoluta" usa o valor como nota.
 * Não depende de pesos nem de filtros: filtrar não muda a nota de ninguém.
 */
export function notasPorIndicador(municipios: Municipio[], config: Config): Map<number, Record<string, number>> {
  const resultado = new Map<number, Record<string, number>>(municipios.map((m) => [m.cod, {}]))
  for (const topico of Object.values(config.topicos)) {
    for (const [indicador, { sentido, escala = 'log' }] of Object.entries(topico.indicadores)) {
      const comDado = municipios.filter((m) => m.indicadores[indicador])
      if (comDado.length === 0) continue
      if (escala === 'absoluta') {
        for (const m of comDado) {
          const v = Math.min(Math.max(m.indicadores[indicador].valor, 0), 100)
          resultado.get(m.cod)![indicador] = sentido === 'menor_melhor' ? 100 - v : v
        }
        continue
      }
      const x = comDado.map((m) => {
        const v = m.indicadores[indicador].valor
        return escala === 'log' ? Math.log1p(v) : escala === 'raiz' ? Math.sqrt(Math.max(v, 0)) : v
      })
      const ordenados = [...x].sort((a, b) => a - b)
      const min = quantil(ordenados, CORTE)
      const max = quantil(ordenados, 1 - CORTE)
      comDado.forEach((m, i) => {
        const relativo = max > min ? (Math.min(Math.max(x[i], min), max) - min) / (max - min) : 0.5
        resultado.get(m.cod)![indicador] = 100 * (sentido === 'menor_melhor' ? 1 - relativo : relativo)
      })
    }
  }
  return resultado
}

function mediaPonderada(itens: [number | null, number][]): number | null {
  const validos = itens.filter(([v, p]) => v !== null && p > 0) as [number, number][]
  const soma = validos.reduce((s, [, p]) => s + p, 0)
  return soma > 0 ? validos.reduce((s, [v, p]) => s + v * p, 0) / soma : null
}

/** Peso de um tópico na nota geral: zero se foi desligado, sem perder o valor do controle. */
export function pesoTopico(pesos: Pesos, topico: string): number {
  return pesos.desligados.includes(topico) ? 0 : pesos.topicos[topico] ?? 0
}

/**
 * Tópicos e indicadores sem dado (ou desligados) ficam de fora da média, e os pesos dos demais são reescalados:
 * cada um herda uma parte do peso que saiu proporcional ao próprio peso.
 * A nota do tópico desligado continua calculada, só não entra na geral.
 */
export function combinarNotas(porIndicador: Record<string, number>, config: Config, pesos: Pesos): Notas {
  const topicos: Record<string, number | null> = {}
  for (const [topico, cfg] of Object.entries(config.topicos)) {
    topicos[topico] = mediaPonderada(
      Object.keys(cfg.indicadores).map((ind) => [porIndicador[ind] ?? null, pesos.indicadores[topico]?.[ind] ?? 0]),
    )
  }
  const geral = mediaPonderada(Object.keys(config.topicos).map((t) => [topicos[t], pesoTopico(pesos, t)]))
  return { geral, topicos, indicadores: porIndicador }
}

export function pesosIniciais(config: Config): Pesos {
  return {
    topicos: Object.fromEntries(Object.entries(config.topicos).map(([t, c]) => [t, c.peso])),
    indicadores: Object.fromEntries(
      Object.entries(config.topicos).map(([t, c]) => [
        t,
        Object.fromEntries(Object.entries(c.indicadores).map(([i, ci]) => [i, ci.peso])),
      ]),
    ),
    desligados: [],
  }
}
