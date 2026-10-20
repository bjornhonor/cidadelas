import type { Config, Municipio, Notas, ValorIndicador } from '../types'
import { TOPICOS, formatarNumero, rotuloIndicador } from '../rotulos'
import { formatarMinutos, type TempoTrabalho } from '../deslocamento'
import { PilulaNota } from './Ranking'

interface Props {
  municipio: Municipio
  notas: Notas
  posicao: number | null
  config: Config
  unidades: Record<string, string>
  tempo: TempoTrabalho | null // até o trabalho, só no modo presencial
  onFechar: () => void
}

/** Linha de apoio abaixo do nome do indicador, com o que cada tópico tem de específico. */
function complemento(v: ValorIndicador, unidade: string): string {
  const partes: string[] = []
  if (v.minutos != null) partes.push(`${formatarNumero(v.minutos)} min de carro, em média, até a mais próxima`)
  if (v.compra_m2 != null) partes.push(`R$ ${formatarNumero(v.compra_m2)} o m² para comprar`)
  if (v.estimado != null) partes.push(v.estimado ? 'moradia estimada (cidade fora do FipeZap)' : 'moradia pelo FipeZap')
  if (v.eventos != null) partes.push(`${formatarNumero(v.eventos)} casos em 5 anos`)
  if (v.bruto != null) partes.push(`sem ajuste: ${formatarNumero(v.bruto, 1)}`)
  if (v.peso_local != null) partes.push(`${formatarNumero(v.peso_local * 100)}% dado local`)
  if (v.mortos) partes.push(`${formatarNumero(v.mortos)} mortos`)
  if (v.ruas_pct != null) partes.push(`${formatarNumero(v.ruas_pct)}% de ruas completas`)
  if (v.veiculos_km != null) partes.push(`${formatarNumero(v.veiculos_km)} carros e motos por km de rua`)
  if (v.minutos == null) partes.push(unidade)
  return partes.join(' · ')
}

export function Detalhe({ municipio: m, notas, posicao, config, unidades, tempo, onFechar }: Props) {
  return (
    <div className="detalhe">
      <div className="detalhe-topo">
        <button type="button" className="link" onClick={onFechar}>← voltar ao ranking</button>
        <h2>{m.nome}</h2>
        <p>{formatarNumero(m.populacao)} habitantes · {m.regiao_imediata} · {m.regiao_intermediaria}</p>
      </div>
      <div className="detalhe-corpo">
        <div className="destaques">
          <div>
            <span className="muted">Nota geral</span>
            <strong>{notas.geral != null ? formatarNumero(notas.geral, 1) : '–'}</strong>
          </div>
          <div>
            <span className="muted">Posição</span>
            <strong>{posicao != null ? `${posicao}º` : 'fora do filtro'}</strong>
          </div>
          {tempo && (
            <div>
              <span className="muted">Até o trabalho</span>
              <strong>{formatarMinutos(tempo.minutos)}</strong>
            </div>
          )}
        </div>
        {tempo && Math.round(tempo.max) - Math.round(tempo.min) >= 5 && (
          <p className="detalhe-nota">
            De carro, sem trânsito, em média: {formatarMinutos(tempo.min)} da parte da cidade mais perto do trabalho,{' '}
            {formatarMinutos(tempo.max)} da mais longe.
          </p>
        )}

        {Object.entries(config.topicos)
          .filter(([t]) => notas.topicos[t] != null)
          .map(([topico, cfg]) => {
            const indicadores = Object.keys(cfg.indicadores).filter((ind) => m.indicadores[ind])
            const temAjuste = indicadores.some((ind) => m.indicadores[ind].peso_local != null)
            return (
              <section key={topico}>
                <h3>
                  {TOPICOS[topico] ?? topico}
                  <PilulaNota valor={notas.topicos[topico]} posicao={null} />
                </h3>
                <table className="tabela-indicadores">
                  <thead>
                    <tr>
                      <th>Indicador</th>
                      <th className="num">Nota</th>
                      <th className="num">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {indicadores.map((ind) => {
                      const v = m.indicadores[ind]
                      return (
                        <tr key={ind}>
                          <td>
                            {rotuloIndicador(ind)}
                            <small className="muted">{complemento(v, unidades[ind] ?? '')}</small>
                          </td>
                          <td className="num forte">{formatarNumero(notas.indicadores[ind], 0)}</td>
                          <td className="num">{formatarNumero(v.valor, v.valor >= 100 ? 0 : 1)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {temAjuste && (
                  <p className="nota-rodape">
                    Taxas por 100 mil hab./ano. "Dado local" é quanto da taxa vem do próprio município; o resto vem da
                    média das outras cidades da região, porque em cidade pequena poucos casos distorcem a conta.
                  </p>
                )}
              </section>
            )
          })}
      </div>
    </div>
  )
}
