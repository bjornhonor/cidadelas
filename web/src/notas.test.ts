import { describe, expect, it } from 'vitest'
import ouro from '../../testes/notas_ouro.json'
import { combinarNotas, contexto, distribuicoes, notasPorIndicador, percentis, pesosIniciais } from './notas'
import type { Config, Escala, Municipio, Sentido } from './types'

const municipio = (cod: number, indicadores: Record<string, number>): Municipio => ({
  cod, nome: `M${cod}`, populacao: 1000, regiao_imediata: 'R', regiao_intermediaria: 'R',
  indicadores: Object.fromEntries(Object.entries(indicadores).map(([k, valor]) => [k, { valor }])),
})

const umIndicador = (sentido: Sentido, escala: Escala, corte?: number): Config => ({
  topicos: { t: { peso: 1, indicadores: { x: { peso: 1, sentido, escala } } } },
  filtros_apenas: [],
  ...(corte != null ? { corte } : {}),
})

describe('notasPorIndicador', () => {
  it('dá as mesmas notas que o arquivo-ouro (o mesmo que o teste do pipeline usa)', () => {
    for (const caso of ouro.casos) {
      const ms = caso.valores.map((v, i) => municipio(i, { x: v }))
      const notas = notasPorIndicador(ms, umIndicador(caso.sentido as Sentido, caso.escala as Escala, caso.corte))
      caso.esperado.forEach((esperado, i) => expect(notas.get(i)!.x, `${caso.nome}, #${i}`).toBeCloseTo(esperado, 5))
    }
  })

  it('sem corte, o pior tira 0 e o melhor 100, em escala linear', () => {
    const ms = [municipio(1, { x: 10 }), municipio(2, { x: 20 }), municipio(3, { x: 40 })]
    const notas = notasPorIndicador(ms, umIndicador('menor_melhor', 'linear', 0))
    expect([1, 2, 3].map((c) => notas.get(c)!.x)).toEqual([100, (100 * 2) / 3, 0])
  })

  it('na escala absoluta usa o valor como nota, limitado a 0..100', () => {
    const ms = [municipio(1, { x: 70 }), municipio(2, { x: 130 }), municipio(3, { x: -5 })]
    const notas = notasPorIndicador(ms, umIndicador('maior_melhor', 'absoluta'))
    expect([1, 2, 3].map((c) => notas.get(c)!.x)).toEqual([70, 100, 0])
  })

  it('quem não tem o dado fica sem nota, e todos iguais tiram 50', () => {
    const ms = [municipio(1, { x: 5 }), municipio(2, { x: 5 }), municipio(3, {})]
    const notas = notasPorIndicador(ms, umIndicador('maior_melhor', 'linear'))
    expect(notas.get(1)!.x).toBe(50)
    expect(notas.get(3)!.x).toBeUndefined()
  })
})

describe('combinarNotas', () => {
  const config: Config = {
    topicos: {
      a: { peso: 3, indicadores: { a1: { peso: 1, sentido: 'maior_melhor' }, a2: { peso: 3, sentido: 'maior_melhor' } } },
      b: { peso: 1, indicadores: { b1: { peso: 1, sentido: 'maior_melhor' } } },
    },
    filtros_apenas: [],
  }
  const pesos = pesosIniciais(config)

  it('faz a média ponderada dos indicadores e depois dos tópicos', () => {
    const n = combinarNotas({ a1: 100, a2: 0, b1: 50 }, config, pesos)
    expect(n.topicos.a).toBe(25)
    expect(n.geral).toBeCloseTo((25 * 3 + 50) / 4)
  })

  it('indicador sem dado sai, e o peso dos outros é reescalado', () => {
    expect(combinarNotas({ a1: 80, b1: 50 }, config, pesos).topicos.a).toBe(80)
  })

  it('tópico desligado continua calculado, mas fica fora da geral', () => {
    const n = combinarNotas({ a1: 100, a2: 100, b1: 0 }, config, { ...pesos, desligados: ['b'] })
    expect(n.topicos.b).toBe(0)
    expect(n.geral).toBe(100)
  })

  it('sem nenhum dado, a geral é null', () => {
    expect(combinarNotas({}, config, pesos).geral).toBeNull()
  })
})

describe('percentis', () => {
  it('vai de 0 a 100 pela posição, empate fica com a média e sem valor fica null', () => {
    const p = percentis(new Map([[1, 10], [2, 20], [3, 20], [4, 30], [5, null]]))
    expect([...p.values()]).toEqual([0, 50, 50, 100, null])
  })

  it('um valor só fica no meio', () => {
    expect(percentis(new Map([[1, 7]])).get(1)).toBe(50)
  })
})

describe('contexto', () => {
  const ordenados = [1, 2, 3, 4, 5]

  it('mediana e fração dos outros que estão piores', () => {
    expect(contexto(ordenados, 5, 'maior_melhor')).toEqual({ mediana: 3, melhorQue: 1 })
    expect(contexto(ordenados, 5, 'menor_melhor')).toEqual({ mediana: 3, melhorQue: 0 })
    expect(contexto(ordenados, 2, 'menor_melhor').melhorQue).toBe(0.75)
  })

  it('empate não conta como pior', () => {
    expect(contexto([1, 3, 3, 3], 3, 'maior_melhor').melhorQue).toBeCloseTo(1 / 3)
    expect(contexto([1, 3, 3, 3], 3, 'menor_melhor').melhorQue).toBe(0)
  })

  it('distribuicoes guarda os valores em ordem, só de quem tem dado', () => {
    const d = distribuicoes([municipio(1, { x: 3 }), municipio(2, {}), municipio(3, { x: 1 })], umIndicador('maior_melhor', 'linear'))
    expect(d.get('x')).toEqual([1, 3])
  })
})
