// Ordenação do ranking por coluna: nota geral, um tópico, população ou trajeto até o trabalho

/** coluna: 'geral', um tópico, 'populacao' ou 'trajeto'. */
export interface Ordem {
  coluna: string
  crescente: boolean
}

export const ORDEM_PADRAO: Ordem = { coluna: 'geral', crescente: false }

export const ehOrdemPadrao = (o: Ordem) => o.coluna === ORDEM_PADRAO.coluna && o.crescente === ORDEM_PADRAO.crescente

/** Clicar numa coluna nova começa pelo melhor: a maior nota, a maior população ou o menor trajeto. */
export function proximaOrdem(atual: Ordem, coluna: string): Ordem {
  if (atual.coluna === coluna) return { coluna, crescente: !atual.crescente }
  return { coluna, crescente: coluna === 'trajeto' }
}

/**
 * Ordena pela coluna; quem não tem valor vai para o fim nos dois sentidos, e o empate fica com a posição no estado.
 * valor(item, coluna) devolve o número da coluna (ou null).
 */
export function ordenar<T extends { posicaoEstado: number }>(
  itens: T[], ordem: Ordem, valor: (item: T, coluna: string) => number | null | undefined,
): T[] {
  const sinal = ordem.crescente ? 1 : -1
  return [...itens].sort((a, b) => {
    const va = valor(a, ordem.coluna)
    const vb = valor(b, ordem.coluna)
    if (va == null || vb == null) return va == null && vb == null ? a.posicaoEstado - b.posicaoEstado : va == null ? 1 : -1
    return va !== vb ? sinal * (va - vb) : a.posicaoEstado - b.posicaoEstado
  })
}
