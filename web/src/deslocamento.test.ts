import { describe, expect, it } from 'vitest'
import { TETO_MINUTOS, distanciaKm, formatarMinutos, temposAteTrabalho, type Deslocamento } from './deslocamento'

describe('formatarMinutos', () => {
  it('minutos, horas e o teto', () => {
    expect(formatarMinutos(42.4)).toBe('42 min')
    expect(formatarMinutos(60)).toBe('1 h')
    expect(formatarMinutos(95)).toBe('1 h 35')
    expect(formatarMinutos(119.6)).toBe('2 h') // 1 h 60 vira 2 h
    expect(formatarMinutos(TETO_MINUTOS)).toBe('3 h+')
  })
})

describe('temposAteTrabalho', () => {
  // Três pontos: dois da cidade 10 (pop 100 e 300) e um da cidade 20; matriz linha = origem, coluna = destino
  const d: Deslocamento = {
    pontos: [
      { cod: 10, pop: 100, lat: -23, lon: -47 },
      { cod: 10, pop: 300, lat: -23.1, lon: -47 },
      { cod: 20, pop: 50, lat: -22, lon: -46 },
    ],
    matriz: Uint8Array.from([
      0, 10, 255,
      12, 0, 255,
      90, 80, 0,
    ]),
    semRota: 255,
  }

  it('prende o trabalho ao ponto mais perto e faz a média pesada pela população', () => {
    const { tempos, kmAtePonto } = temposAteTrabalho(d, -23, -47) // em cima do ponto 0
    expect(kmAtePonto).toBe(0)
    expect(tempos.get(10)).toEqual({ minutos: (12 * 300) / 400, min: 0, max: 12 }) // o ponto 0 (pop 100) leva 0 min
    expect(tempos.get(20)!.minutos).toBe(90)
  })

  it('sem rota conta como o teto de 3 h', () => {
    const { tempos } = temposAteTrabalho(d, -22, -46) // em cima do ponto 2
    expect(tempos.get(10)!.minutos).toBe(TETO_MINUTOS)
  })

  it('soma o trecho final entre o local e o ponto (linha reta × 1,3 a 30 km/h)', () => {
    const { tempos, kmAtePonto } = temposAteTrabalho(d, -23.01, -47)
    expect(kmAtePonto).toBeCloseTo(distanciaKm(-23.01, -47, -23, -47))
    expect(tempos.get(20)!.minutos).toBeCloseTo(90 + (kmAtePonto * 1.3) / 0.5)
  })
})
