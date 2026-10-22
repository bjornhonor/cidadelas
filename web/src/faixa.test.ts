import { describe, expect, it } from 'vitest'
import { faixasDePosicao, gama, gerador } from './faixa'

describe('gerador e gama', () => {
  it('a mesma semente dá a mesma sequência', () => {
    const [a, b] = [gerador(7), gerador(7)]
    expect([a(), a(), a()]).toEqual([b(), b(), b()])
  })

  it('a Gama tem média perto da forma, inclusive com forma abaixo de 1', () => {
    for (const forma of [0.5, 3, 30]) {
      const aleatorio = gerador(forma * 100)
      const n = 20000
      let soma = 0
      for (let i = 0; i < n; i++) soma += gama(forma, aleatorio)
      expect(soma / n).toBeCloseTo(forma, forma < 1 ? 1 : 0)
    }
  })
})

describe('faixasDePosicao', () => {
  const topicos = new Map<number, Record<string, number | null>>([
    [1, { a: 100, b: 100 }], // melhor em tudo
    [2, { a: 90, b: 10 }], // depende do peso
    [3, { a: 10, b: 90 }],
    [4, { a: 0, b: null }], // sem b: entra só com a
  ])

  it('quem é melhor em tudo fica sempre em 1º; quem depende do peso tem faixa larga', () => {
    const f = faixasDePosicao(topicos, { a: 50, b: 50 }, { concentracao: 5 })
    expect(f.get(1)).toEqual([1, 1])
    expect(f.get(2)![0]).toBe(2)
    expect(f.get(2)![1]).toBe(3)
    expect(f.get(4)).toEqual([4, 4])
  })

  it('é determinística e ignora tópico com peso zero', () => {
    const f1 = faixasDePosicao(topicos, { a: 30, b: 0 })
    expect(f1).toEqual(faixasDePosicao(topicos, { a: 30, b: 0 }))
    expect(f1.get(2)).toEqual([2, 2]) // só "a" conta: 100, 90, 10, 0
  })

  it('sem peso nenhum devolve vazio', () => {
    expect(faixasDePosicao(topicos, { a: 0, b: 0 }).size).toBe(0)
  })
})
