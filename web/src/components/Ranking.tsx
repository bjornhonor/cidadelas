import { useState } from 'react'
import type { Municipio, Notas } from '../types'
import { TOPICOS, TOPICOS_CURTOS, formatarNumero } from '../rotulos'
import { formatarMinutos, type TempoTrabalho } from '../deslocamento'
import { ehOrdemPadrao, proximaOrdem, type Ordem } from '../ordem'

export interface LinhaRanking {
  posicao: number // ordem dentro do filtro, na ordenação escolhida
  posicaoEstado: number // entre todos os municípios (ou todas as zonas), pela nota geral: é a que aparece
  municipio: Municipio
  notas: Notas
}

interface Props {
  linhas: LinhaRanking[]
  topicos: string[]
  tempos: Map<number, TempoTrabalho> | null // só no modo presencial
  cidade: string | null // dentro de uma cidade, as linhas são zonas
  selecionado: number | null
  ordem: Ordem
  onOrdenar: (o: Ordem) => void
  onSelecionar: (cod: number) => void
}

const POR_PAGINA = 25
const NOTA_ALTA = 80 // nota de tópico a partir da qual a célula ganha destaque
const PERTO_MIN = 60 // trajeto até aqui aparece em verde

const nota = (v: number | null) => (v == null ? '–' : formatarNumero(v, 1))

/** Pílula da nota geral: o 1º em menta cheia, 2º e 3º um tom abaixo. */
export function PilulaNota({ valor, posicao }: { valor: number | null; posicao: number | null }) {
  const nivel = valor == null ? 'vazia' : posicao === 1 ? 'n1' : posicao != null && posicao <= 3 ? 'n2' : ''
  return <span className={`pilula-nota ${nivel}`}>{nota(valor)}</span>
}

/** Moradia estimada pelo Censo 2010 (cidade fora do FipeZap): o custo vem com um "≈". */
export function SeloEstimado({ municipio }: { municipio: Municipio }) {
  if (!municipio.indicadores.cesta_mensal?.estimado) return null
  return <span className="estimado" title="custo com moradia estimada (cidade fora do FipeZap)">≈</span>
}

function milHabitantes(p: number) {
  return p >= 1_000_000
    ? `${formatarNumero(p / 1_000_000, 1)} mi hab.`
    : p >= 1_000 ? `${formatarNumero(p / 1_000)} mil hab.` : `${formatarNumero(p)} hab.`
}

export function Ranking({ linhas, topicos, tempos, cidade, selecionado, ordem, onOrdenar, onSelecionar }: Props) {
  const [pagina, setPagina] = useState(1)
  const paginas = Math.max(1, Math.ceil(linhas.length / POR_PAGINA))
  const atual = Math.min(pagina, paginas) // o filtro pode encolher a lista enquanto se está numa página adiante
  const inicio = (atual - 1) * POR_PAGINA
  const visiveis = linhas.slice(inicio, inicio + POR_PAGINA)
  const padrao = ehOrdemPadrao(ordem)
  const rotuloColuna = (c: string) =>
    c === 'geral' ? 'nota geral' : c === 'populacao' ? 'habitantes' : c === 'trajeto' ? 'trajeto' : TOPICOS[c] ?? c

  // Cabeçalho clicável: o botão ordena, e o aria-sort diz a ordem atual a quem usa leitor de tela
  const cabecalho = (coluna: string, texto: string, classe: string, titulo?: string) => {
    const ativa = ordem.coluna === coluna
    return (
      <th
        key={coluna} className={`${classe} ordenavel ${ativa ? 'ativa' : ''}`} title={titulo}
        aria-sort={ativa ? (ordem.crescente ? 'ascending' : 'descending') : 'none'}
      >
        <button type="button" onClick={() => onOrdenar(proximaOrdem(ordem, coluna))}>
          {texto}{ativa && <span aria-hidden>{ordem.crescente ? ' ↑' : ' ↓'}</span>}
        </button>
      </th>
    )
  }

  return (
    <div className="ranking">
      <div className="ranking-topo">
        <div>
          <h2>{cidade ? `Zonas de ${cidade}` : 'Ranking dos Municípios'}</h2>
          <p>
            {!padrao
              ? `Ordenado por ${rotuloColuna(ordem.coluna)} (${ordem.crescente ? 'menor' : 'maior'} primeiro)`
              : cidade ? 'Notas comparando só as zonas entre si (a pior tira 0, a melhor 100)' : 'Ordenado pela nota com os pesos escolhidos'}
          </p>
        </div>
        <span className="aptas">{linhas.length} aptas</span>
      </div>

      {/* O pódio é dos três melhores pela nota geral; em outra ordenação ele sai para não confundir */}
      {linhas.length > 0 && padrao && (
        <div className="podio">
          {linhas.slice(0, 3).map(({ posicao, posicaoEstado, municipio: m, notas }) => (
            <button
              key={m.cod} type="button" className={posicao === 1 ? 'primeiro' : ''}
              onClick={() => onSelecionar(m.cod)}
            >
              <span className="podio-lugar">{posicaoEstado}º</span>
              <div>
                <h3>{m.nome}</h3>
                <small>{milHabitantes(m.populacao)}</small>
              </div>
              <div className="podio-base">
                <span className="podio-nota">{nota(notas.geral)}</span>
                <span className="barrinhas" aria-hidden>
                  {topicos.map((t) => (
                    <span
                      key={t} title={`${TOPICOS[t] ?? t}: ${nota(notas.topicos[t])}`}
                      style={{ height: `${Math.max(notas.topicos[t] ?? 0, 10)}%` }}
                    />
                  ))}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="tabela-rolagem">
        <table>
          <thead>
            <tr>
              <th title={cidade ? 'posição entre todas as zonas' : 'posição no estado (não muda com o filtro)'}>#</th>
              <th>{cidade ? 'Zona' : 'Cidade'}</th>
              {cabecalho('populacao', 'Habitantes', 'num')}
              {tempos && cabecalho('trajeto', 'Trajeto', 'num', 'de carro, sem trânsito')}
              {cabecalho('geral', 'Geral', 'num geral')}
              {topicos.map((t) => cabecalho(
                t, TOPICOS_CURTOS[t] ?? t, 'num',
                t === 'custo' && !cidade ? 'Custo de vida (≈: moradia estimada, cidade fora do FipeZap)' : TOPICOS[t],
              ))}
            </tr>
          </thead>
          <tbody>
            {visiveis.map(({ posicaoEstado: posicao, municipio: m, notas }) => {
              const tempo = tempos?.get(m.cod)
              const selecionada = m.cod === selecionado
              return (
                <tr
                  key={m.cod}
                  className={selecionada ? 'selecionada' : ''}
                  tabIndex={0}
                  aria-selected={selecionada}
                  aria-label={`${m.nome}, ${posicao}º, nota ${nota(notas.geral)}`}
                  onClick={() => onSelecionar(m.cod)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onSelecionar(m.cod)
                    }
                  }}
                >
                  <td>{posicao}</td>
                  <td className="cidade">
                    {m.nome}
                    {selecionada && <span className="ponto-selecionado" />}
                  </td>
                  <td className="num">{formatarNumero(m.populacao)}</td>
                  {tempos && (
                    <td className={`num ${tempo && tempo.minutos <= PERTO_MIN ? 'perto' : ''}`}>
                      {tempo ? formatarMinutos(tempo.minutos) : '–'}
                    </td>
                  )}
                  <td className="num geral"><PilulaNota valor={notas.geral} posicao={posicao} /></td>
                  {topicos.map((t) => {
                    const v = notas.topicos[t]
                    return (
                      <td key={t} className={`num ${v != null && v >= NOTA_ALTA ? 'destaque' : ''}`}>
                        {t === 'custo' && <SeloEstimado municipio={m} />}{nota(v)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
        {linhas.length === 0 && <p className="vazio">Nenhuma {cidade ? 'zona' : 'cidade'} com esses filtros.</p>}
      </div>

      <div className="paginacao">
        <span>
          {linhas.length ? `Exibindo ${inicio + 1}–${inicio + visiveis.length} de ${linhas.length}` : `Nenhuma ${cidade ? 'zona' : 'cidade'}`}
        </span>
        <div>
          <button type="button" disabled={atual <= 1} onClick={() => setPagina(atual - 1)}>Anterior</button>
          <strong>{atual}</strong>
          <button type="button" disabled={atual >= paginas} onClick={() => setPagina(atual + 1)}>Próximo</button>
        </div>
      </div>
    </div>
  )
}
