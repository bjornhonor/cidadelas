// Estado da tela no endereço, para dar para copiar e mandar o link: pesos, filtros, cidade aberta, cor do mapa,
// ordenação e comparação. Só vai para o endereço o que difere do padrão, então o link fica curto.
// O local de trabalho não entra: é um dado pessoal, e cada um marca o seu.
//
//   #?p.seguranca=40&fora=custo&reg=Campinas&sel=3556206
//   #cidade/valinhos?p.seguranca.roubo=70&ord=saude.asc

import type { Filtros } from './components/Controles'
import { ORDEM_PADRAO, ehOrdemPadrao, type Ordem } from './ordem'
import type { Pesos } from './types'

export interface EstadoVisao {
  pesos: Pesos
  filtros: Filtros
  selecionado: number | null
  corPor: string
  ordem: Ordem
  comparando: number[] // até MAX_COMPARAR códigos
  vendoComparacao: boolean
}

export const MAX_COMPARAR = 3
export const FILTROS_VAZIOS: Filtros = { populacaoMin: 0, regiao: '', busca: '', tempoMax: 0 }

/** "#cidade/valinhos?x=1" → slug "valinhos"; "#?x=1", "#" ou "" → slug null (o estado). */
export function lerHash(hash: string): { slug: string | null; params: URLSearchParams } {
  const [caminho, consulta = ''] = hash.replace(/^#/, '').split('?', 2)
  const slug = /^cidade\/([a-z0-9-]+)$/.exec(caminho)?.[1] ?? null
  return { slug, params: new URLSearchParams(consulta) }
}

export function montarHash(slug: string | null, params: URLSearchParams): string {
  const consulta = params.toString()
  const caminho = slug ? `cidade/${slug}` : ''
  return caminho || consulta ? `#${caminho}${consulta ? `?${consulta}` : ''}` : ''
}

const numero = (texto: string | null) => {
  const v = texto == null || texto === '' ? NaN : Number(texto)
  return Number.isFinite(v) ? v : null
}
const peso = (texto: string | null) => {
  const v = numero(texto)
  return v == null ? null : Math.min(Math.max(Math.round(v), 0), 100)
}

/**
 * Lê o estado do endereço por cima de `base` (o que vale sem link: pesos salvos, filtros vazios...).
 * Pesos no endereço são diferenças em relação a `padrao` (o config); se houver algum, eles mandam.
 * Chave ou valor desconhecido é ignorado, para um link velho não quebrar a tela.
 */
export function lerEstado(params: URLSearchParams, base: EstadoVisao, padrao: Pesos): EstadoVisao {
  const temPesos = [...params.keys()].some((k) => k.startsWith('p.')) || params.has('fora')
  let pesos = base.pesos
  if (temPesos) {
    pesos = {
      topicos: Object.fromEntries(Object.entries(padrao.topicos).map(([t, v]) => [t, peso(params.get(`p.${t}`)) ?? v])),
      indicadores: Object.fromEntries(Object.entries(padrao.indicadores).map(([t, inds]) => [
        t, Object.fromEntries(Object.entries(inds).map(([i, v]) => [i, peso(params.get(`p.${t}.${i}`)) ?? v])),
      ])),
      desligados: (params.get('fora') ?? '').split(',').filter((t) => t in padrao.topicos),
    }
  }

  const [coluna, sentido] = (params.get('ord') ?? '').split('.')
  const ordem: Ordem = coluna ? { coluna, crescente: sentido === 'asc' } : base.ordem
  const comparando = (params.get('cmp') ?? '').split(',').map(numero).filter((v): v is number => v != null)

  return {
    pesos,
    filtros: {
      populacaoMin: numero(params.get('pop')) ?? base.filtros.populacaoMin,
      regiao: params.get('reg') ?? base.filtros.regiao,
      busca: params.get('q') ?? base.filtros.busca,
      tempoMax: numero(params.get('tmax')) ?? base.filtros.tempoMax,
    },
    selecionado: numero(params.get('sel')) ?? base.selecionado,
    corPor: params.get('cor') ?? base.corPor,
    ordem,
    comparando: comparando.length ? [...new Set(comparando)].slice(0, MAX_COMPARAR) : base.comparando,
    vendoComparacao: params.get('ver') === 'cmp' || base.vendoComparacao,
  }
}

/** O contrário de lerEstado: só o que difere do padrão (pesos do config, filtros vazios, nota geral...). */
export function escreverEstado(e: EstadoVisao, padrao: Pesos): URLSearchParams {
  const p = new URLSearchParams()
  for (const [t, v] of Object.entries(e.pesos.topicos)) if (v !== padrao.topicos[t]) p.set(`p.${t}`, String(v))
  for (const [t, inds] of Object.entries(e.pesos.indicadores)) {
    for (const [i, v] of Object.entries(inds)) if (v !== padrao.indicadores[t]?.[i]) p.set(`p.${t}.${i}`, String(v))
  }
  if (e.pesos.desligados.length) p.set('fora', e.pesos.desligados.join(','))
  if (e.filtros.populacaoMin) p.set('pop', String(e.filtros.populacaoMin))
  if (e.filtros.regiao) p.set('reg', e.filtros.regiao)
  if (e.filtros.busca) p.set('q', e.filtros.busca)
  if (e.filtros.tempoMax) p.set('tmax', String(e.filtros.tempoMax))
  if (e.selecionado != null) p.set('sel', String(e.selecionado))
  if (e.corPor !== 'geral') p.set('cor', e.corPor)
  if (!ehOrdemPadrao(e.ordem)) p.set('ord', `${e.ordem.coluna}${e.ordem.crescente ? '.asc' : ''}`)
  if (e.comparando.length) p.set('cmp', e.comparando.join(','))
  if (e.vendoComparacao && e.comparando.length) p.set('ver', 'cmp')
  return p
}

export const ESTADO_VAZIO = (pesos: Pesos): EstadoVisao => ({
  pesos, filtros: FILTROS_VAZIOS, selecionado: null, corPor: 'geral', ordem: ORDEM_PADRAO,
  comparando: [], vendoComparacao: false,
})
