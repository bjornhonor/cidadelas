import type { Config, Municipio, Notas } from '../types'
import { TOPICOS, formatarNumero, rotuloIndicador } from '../rotulos'
import { PilulaNota, SeloEstimado } from './Ranking'

interface Props {
  municipios: Municipio[] // na ordem em que entraram na comparação
  notas: Map<number, Notas>
  posicoes: Map<number, number> // no estado (ou entre as zonas)
  faixas: Map<number, [number, number]> | null
  total: number
  config: Config
  unidades: Record<string, string>
  zona: boolean
  onAbrir: (cod: number) => void
  onRemover: (cod: number) => void
  onFechar: () => void
}

const nota = (v: number | null | undefined) => (v == null ? '–' : formatarNumero(v, 1))

/** Índice de quem tem a maior nota na linha (null se ninguém tem nota ou se todos empatam). */
function melhor(valores: (number | null | undefined)[]): number | null {
  const com = valores.flatMap((v, i) => (v == null ? [] : [[v, i] as const]))
  if (com.length < 2) return null
  const max = Math.max(...com.map(([v]) => v))
  const lideres = com.filter(([v]) => v === max)
  return lideres.length === 1 ? lideres[0][1] : null
}

/** Duas ou três cidades lado a lado: posição, nota geral, tópicos e indicadores; a melhor de cada linha em destaque. */
export function Comparacao({ municipios, notas, posicoes, faixas, total, config, unidades, zona, onAbrir, onRemover, onFechar }: Props) {
  const ns = municipios.map((m) => notas.get(m.cod)!)
  const celula = (i: number, destaque: number | null) => (i === destaque ? 'num melhor' : 'num')
  const topicos = Object.entries(config.topicos).filter(([t]) => ns.some((n) => n.topicos[t] != null))

  return (
    <div className="detalhe comparacao">
      <div className="detalhe-topo">
        <button type="button" className="link" onClick={onFechar}>← voltar</button>
        <h2>Comparação</h2>
        <p>
          {municipios.length < 2
            ? `Abra outra ${zona ? 'zona' : 'cidade'} e clique em "+ Comparar" para pôr lado a lado (até 3).`
            : 'Em destaque, a melhor nota de cada linha.'}
        </p>
      </div>
      <div className="detalhe-corpo">
        <table className="tabela-indicadores tabela-comparacao">
          <thead>
            <tr>
              <th />
              {municipios.map((m) => (
                <th key={m.cod} className="num">
                  <button type="button" className="link" onClick={() => onAbrir(m.cod)} title="abrir o detalhe">{m.nome}</button>
                  <button
                    type="button" className="remover" aria-label={`tirar ${m.nome} da comparação`}
                    onClick={() => onRemover(m.cod)}
                  >×</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Posição</td>
              {municipios.map((m) => {
                const f = faixas?.get(m.cod)
                return (
                  <td key={m.cod} className="num">
                    <strong>{posicoes.get(m.cod)}º</strong> de {total}
                    {f && f[0] !== f[1] && <small>faixa {f[0]}º–{f[1]}º</small>}
                  </td>
                )
              })}
            </tr>
            <tr>
              <td>Habitantes</td>
              {municipios.map((m) => <td key={m.cod} className="num">{formatarNumero(m.populacao)}</td>)}
            </tr>
            <tr className="linha-geral">
              <td>Nota geral</td>
              {municipios.map((m, i) => (
                <td key={m.cod} className="num">
                  <PilulaNota valor={ns[i].geral} posicao={i === melhor(ns.map((n) => n.geral)) ? 1 : null} />
                </td>
              ))}
            </tr>
            {topicos.map(([topico, cfg]) => {
              const destaque = melhor(ns.map((n) => n.topicos[topico]))
              return [
                <tr key={topico} className="linha-topico">
                  <td>{TOPICOS[topico] ?? topico}</td>
                  {municipios.map((m, i) => (
                    <td key={m.cod} className={celula(i, destaque)}>
                      {topico === 'custo' && <SeloEstimado municipio={m} />}{nota(ns[i].topicos[topico])}
                    </td>
                  ))}
                </tr>,
                ...Object.keys(cfg.indicadores)
                  .filter((ind) => municipios.some((m) => m.indicadores[ind]))
                  .map((ind) => {
                    const d = melhor(ns.map((n) => n.indicadores[ind]))
                    return (
                      <tr key={ind}>
                        <td title={unidades[ind]}>{rotuloIndicador(ind)}</td>
                        {municipios.map((m, i) => {
                          const v = m.indicadores[ind]
                          return (
                            <td key={m.cod} className={celula(i, d)}>
                              {nota(ns[i].indicadores[ind])}
                              {/* Na escala absoluta o valor já é a nota: não repete */}
                              {v && cfg.indicadores[ind].escala !== 'absoluta' && (
                                <small>{formatarNumero(v.valor, v.valor >= 100 ? 0 : 1)}</small>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  }),
              ]
            })}
          </tbody>
        </table>
        <p className="nota-rodape">
          Em cada linha, a nota (0 a 100) e, embaixo, o valor original. Passe o mouse no nome do indicador para ver a
          unidade.
        </p>
      </div>
    </div>
  )
}
