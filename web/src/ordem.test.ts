import { describe, expect, it } from 'vitest'
import { ORDEM_PADRAO, ordenar, proximaOrdem } from './ordem'

const itens = [
  { nome: 'a', posicaoEstado: 1, v: 10 },
  { nome: 'b', posicaoEstado: 2, v: null },
  { nome: 'c', posicaoEstado: 3, v: 30 },
  { nome: 'd', posicaoEstado: 4, v: 10 },
]
const nomes = (xs: typeof itens) => xs.map((x) => x.nome).join('')

describe('ordenar', () => {
  it('sem valor vai para o fim nos dois sentidos; empate fica com a posição no estado', () => {
    expect(nomes(ordenar(itens, { coluna: 'v', crescente: false }, (x) => x.v))).toBe('cadb')
    expect(nomes(ordenar(itens, { coluna: 'v', crescente: true }, (x) => x.v))).toBe('adcb')
  })

  it('não mexe na lista original', () => {
    ordenar(itens, ORDEM_PADRAO, (x) => x.v)
    expect(nomes(itens)).toBe('abcd')
  })
})

describe('proximaOrdem', () => {
  it('a mesma coluna inverte; coluna nova começa pelo melhor', () => {
    expect(proximaOrdem(ORDEM_PADRAO, 'geral')).toEqual({ coluna: 'geral', crescente: true })
    expect(proximaOrdem(ORDEM_PADRAO, 'saude')).toEqual({ coluna: 'saude', crescente: false })
    expect(proximaOrdem(ORDEM_PADRAO, 'trajeto')).toEqual({ coluna: 'trajeto', crescente: true })
  })
})
