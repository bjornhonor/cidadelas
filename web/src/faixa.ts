// Faixa de posição: o quanto a posição de cada cidade depende do peso exato dos tópicos.
// Sorteia pesos em volta dos escolhidos (Dirichlet: com concentração 100, um tópico de peso 30% varia uns 15% para
// cima ou para baixo, um de 10%, uns 30%), refaz a nota geral e a ordem, e guarda a posição de cada sorteio.
// A faixa é do 5º ao 95º percentil das posições. Semente fixa: a mesma entrada dá sempre a mesma faixa.

export interface OpcoesFaixa {
  sorteios: number
  concentracao: number
  semente: number
}

const PADRAO: OpcoesFaixa = { sorteios: 300, concentracao: 100, semente: 1 }

/** Gerador pseudoaleatório pequeno e com semente (mulberry32): uniforme em [0, 1). */
export function gerador(semente: number): () => number {
  let a = semente >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function normal(aleatorio: () => number): number {
  const u = 1 - aleatorio() // (0, 1]: sem log de zero
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * aleatorio())
}

/** Sorteio da distribuição Gama(forma, 1), pelo método de Marsaglia e Tsang. */
export function gama(forma: number, aleatorio: () => number): number {
  if (forma < 1) return gama(forma + 1, aleatorio) * aleatorio() ** (1 / forma)
  const d = forma - 1 / 3
  const c = 1 / Math.sqrt(9 * d)
  for (;;) {
    let x: number
    let v: number
    do {
      x = normal(aleatorio)
      v = 1 + c * x
    } while (v <= 0)
    v = v ** 3
    const u = aleatorio()
    if (Math.log(u) < 0.5 * x * x + d - d * v + d * Math.log(v)) return d * v
  }
}

/**
 * topicos: nota de cada tópico por código (null = sem dado, fica de fora como na nota geral).
 * pesos: peso de cada tópico (0 = desligado). Devolve, por código, [melhor, pior] posição da faixa.
 */
export function faixasDePosicao(
  topicos: Map<number, Record<string, number | null>>,
  pesos: Record<string, number>,
  opcoes: Partial<OpcoesFaixa> = {},
): Map<number, [number, number]> {
  const { sorteios, concentracao, semente } = { ...PADRAO, ...opcoes }
  const nomes = Object.keys(pesos).filter((t) => pesos[t] > 0)
  const soma = nomes.reduce((s, t) => s + pesos[t], 0)
  const codigos = [...topicos.keys()]
  const resultado = new Map<number, [number, number]>()
  if (!soma || !codigos.length) return resultado

  const notas = codigos.map((cod) => nomes.map((t) => topicos.get(cod)![t] ?? null))
  const posicoes = codigos.map(() => new Int32Array(sorteios))
  const aleatorio = gerador(semente)
  const geral = new Float64Array(codigos.length)
  const ordem = codigos.map((_, i) => i)

  for (let s = 0; s < sorteios; s++) {
    const w = nomes.map((t) => gama((concentracao * pesos[t]) / soma, aleatorio))
    notas.forEach((n, i) => {
      let num = 0
      let den = 0
      n.forEach((v, j) => {
        if (v != null) {
          num += v * w[j]
          den += w[j]
        }
      })
      geral[i] = den > 0 ? num / den : -1 // sem nota vai para o fim, como no ranking
    })
    ordem.sort((a, b) => geral[b] - geral[a] || a - b)
    ordem.forEach((i, p) => {
      posicoes[i][s] = p + 1
    })
  }

  codigos.forEach((cod, i) => {
    const ps = posicoes[i].sort()
    resultado.set(cod, [ps[Math.floor(0.05 * (sorteios - 1))], ps[Math.ceil(0.95 * (sorteios - 1))]])
  })
  return resultado
}
