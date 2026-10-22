import { describe, expect, it } from 'vitest'
import { pesosIniciais } from './notas'
import { ESTADO_VAZIO, escreverEstado, lerEstado, lerHash, montarHash, type EstadoVisao } from './url'
import type { Config } from './types'

const config: Config = {
  topicos: {
    seguranca: { peso: 30, indicadores: { roubo: { peso: 40, sentido: 'menor_melhor' }, letal: { peso: 60, sentido: 'menor_melhor' } } },
    custo: { peso: 15, indicadores: { cesta: { peso: 100, sentido: 'menor_melhor' } } },
  },
  filtros_apenas: [],
}
const padrao = pesosIniciais(config)

describe('lerHash e montarHash', () => {
  it('separa a cidade dos parâmetros', () => {
    expect(lerHash('#cidade/valinhos?sel=3').slug).toBe('valinhos')
    expect(lerHash('#cidade/valinhos?sel=3').params.get('sel')).toBe('3')
    expect(lerHash('#?sel=3').slug).toBeNull()
    expect(lerHash('').slug).toBeNull()
  })

  it('sem nada a guardar, o estado fica sem hash', () => {
    expect(montarHash(null, new URLSearchParams())).toBe('')
    expect(montarHash('valinhos', new URLSearchParams())).toBe('#cidade/valinhos')
    expect(montarHash(null, new URLSearchParams({ sel: '3' }))).toBe('#?sel=3')
  })
})

describe('estado no endereço', () => {
  it('o estado padrão não escreve nada', () => {
    expect(escreverEstado(ESTADO_VAZIO(padrao), padrao).toString()).toBe('')
  })

  it('ida e volta guardam pesos, filtros, seleção, ordem e comparação', () => {
    const estado: EstadoVisao = {
      pesos: {
        topicos: { seguranca: 50, custo: 15 },
        indicadores: { seguranca: { roubo: 70, letal: 60 }, custo: { cesta: 100 } },
        desligados: ['custo'],
      },
      filtros: { populacaoMin: 10000, regiao: 'São José do Rio Preto', busca: 'jardim', tempoMax: 45 },
      selecionado: 3556206,
      corPor: 'saude',
      ordem: { coluna: 'saude', crescente: true },
      comparando: [3556206, 3509502],
      vendoComparacao: true,
    }
    const params = escreverEstado(estado, padrao)
    expect(params.get('p.seguranca')).toBe('50')
    expect(params.has('p.custo')).toBe(false) // igual ao padrão
    const volta = lerEstado(new URLSearchParams(params.toString()), ESTADO_VAZIO(padrao), padrao)
    expect(volta).toEqual(estado)
  })

  it('pesos do link mandam sobre os salvos; sem pesos no link, valem os salvos', () => {
    const salvos = { ...padrao, topicos: { seguranca: 10, custo: 90 } }
    expect(lerEstado(new URLSearchParams('p.custo=40'), ESTADO_VAZIO(salvos), padrao).pesos.topicos)
      .toEqual({ seguranca: 30, custo: 40 })
    expect(lerEstado(new URLSearchParams('sel=1'), ESTADO_VAZIO(salvos), padrao).pesos).toBe(salvos)
  })

  it('valor inválido ou desconhecido é ignorado', () => {
    const e = lerEstado(new URLSearchParams('p.seguranca=abc&p.inexistente=5&fora=custo,nada&sel=x&cmp=1,1,2,3,4'),
      ESTADO_VAZIO(padrao), padrao)
    expect(e.pesos.topicos.seguranca).toBe(30)
    expect(e.pesos.desligados).toEqual(['custo'])
    expect(e.selecionado).toBeNull()
    expect(e.comparando).toEqual([1, 2, 3]) // sem repetir e no máximo 3
  })

  it('peso fora de 0..100 é limitado', () => {
    expect(lerEstado(new URLSearchParams('p.seguranca=250'), ESTADO_VAZIO(padrao), padrao).pesos.topicos.seguranca).toBe(100)
  })
})
