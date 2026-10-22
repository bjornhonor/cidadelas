import { useEffect, useState, type ReactNode } from 'react'
import type { Config, Pesos } from '../types'
import { TOPICOS, rotuloIndicador } from '../rotulos'
import { pesoTopico } from '../notas'
import { IconeLupa, IconeSeta, IconeTopico } from './Icones'

export interface Filtros {
  populacaoMin: number
  regiao: string
  busca: string
  tempoMax: number // minutos de carro até o trabalho; 0 = sem limite
}

const FAIXAS_POPULACAO = [0, 5_000, 10_000, 20_000, 50_000, 100_000, 500_000]

interface Props {
  trabalho: ReactNode // seção do local de trabalho, antes dos filtros
  cidade: string | null // dentro de uma cidade: só a busca por zona ou bairro
  config: Config
  pesos: Pesos
  topicosComDado: Set<string>
  indicadoresComDado: Set<string>
  regioes: string[]
  filtros: Filtros
  aptas: number // cidades que passam nos filtros
  total: number
  onPesos: (p: Pesos) => void
  onFiltros: (f: Filtros) => void
  onRestaurarPesos: () => void
}

/** Campo para digitar o peso. Guarda o texto enquanto se digita, para dar para apagar e escrever outro número. */
function NumeroPeso({ rotulo, valor, desabilitado, onChange }: {
  rotulo: string
  valor: number
  desabilitado?: boolean
  onChange: (v: number) => void
}) {
  const [texto, setTexto] = useState(String(valor))
  useEffect(() => setTexto(String(valor)), [valor])

  return (
    <input
      type="number" className="peso-valor" min={0} max={100} step={1} inputMode="numeric"
      value={texto} disabled={desabilitado} aria-label={`peso de ${rotulo} (número)`}
      onChange={(e) => {
        setTexto(e.target.value)
        const v = Number(e.target.value)
        if (e.target.value !== '' && Number.isFinite(v)) onChange(Math.min(Math.max(Math.round(v), 0), 100))
      }}
      onBlur={() => setTexto(String(valor))}
      onFocus={(e) => e.target.select()}
    />
  )
}

export function Controles(props: Props) {
  const { config, pesos, topicosComDado, indicadoresComDado, regioes, filtros, onPesos, onFiltros } = props
  const [aberto, setAberto] = useState<string | null>('seguranca')

  const mudarTopico = (t: string, v: number) => onPesos({ ...pesos, topicos: { ...pesos.topicos, [t]: v } })
  const mudarIndicador = (t: string, i: string, v: number) =>
    onPesos({ ...pesos, indicadores: { ...pesos.indicadores, [t]: { ...pesos.indicadores[t], [i]: v } } })
  const ligarTopico = (t: string, ligado: boolean) =>
    onPesos({ ...pesos, desligados: ligado ? pesos.desligados.filter((d) => d !== t) : [...pesos.desligados, t] })

  // Peso efetivo: o tópico desligado (ou sem dado) sai, e o resto é reescalado para somar 100%
  const somaAtivos = [...topicosComDado].reduce((s, t) => s + pesoTopico(pesos, t), 0)
  const efetivo = (t: string) =>
    topicosComDado.has(t) && somaAtivos > 0 ? Math.round((100 * pesoTopico(pesos, t)) / somaAtivos) : null

  return (
    <aside className="controles" id="controles">
      {props.trabalho}

      <section className="cartao">
        <div className="cartao-titulo">
          <h2>Filtros territoriais</h2>
          <span className="contagem">{props.aptas} / {props.total} aptas</span>
        </div>
        <div className="com-icone">
          <IconeLupa />
          <input
            type="search" className="entrada" value={filtros.busca}
            aria-label={props.cidade ? 'Buscar zona ou bairro' : 'Buscar município'}
            placeholder={props.cidade ? 'Buscar zona ou bairro (ex.: Centro, Macuco…)' : 'Buscar município (ex.: Botucatu, Atibaia…)'}
            onChange={(e) => onFiltros({ ...filtros, busca: e.target.value })}
          />
        </div>
        {!props.cidade && <div className="duas-colunas">
          <label className="campo">
            <span className="rotulo-pequeno">População mínima</span>
            <select
              className="seletor" value={filtros.populacaoMin}
              onChange={(e) => onFiltros({ ...filtros, populacaoMin: Number(e.target.value) })}
            >
              {FAIXAS_POPULACAO.map((p) => (
                <option key={p} value={p}>{p === 0 ? 'Todas' : `${p.toLocaleString('pt-BR')}+ hab.`}</option>
              ))}
            </select>
          </label>
          <label className="campo">
            <span className="rotulo-pequeno">Região</span>
            <select
              className="seletor" value={filtros.regiao}
              onChange={(e) => onFiltros({ ...filtros, regiao: e.target.value })}
            >
              <option value="">Todo o estado</option>
              {regioes.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
        </div>}
      </section>

      <section className="cartao">
        <div className="cartao-titulo">
          <h2>
            Pesos de decisão
            <span className="ajuda" title="Ajuste a relevância de cada tópico na nota geral">?</span>
          </h2>
          <button type="button" className="link" onClick={props.onRestaurarPesos}>restaurar</button>
        </div>
        {Object.entries(config.topicos).map(([topico, cfg]) => {
          const temDado = topicosComDado.has(topico)
          const ligado = !pesos.desligados.includes(topico)
          const expandido = temDado && aberto === topico
          const rotulo = TOPICOS[topico] ?? topico
          const classes = ['topico', expandido && 'aberto', !temDado && 'sem-dado', !ligado && 'desligado']
          return (
            <div key={topico} className={classes.filter(Boolean).join(' ')}>
              <div className="topico-cabecalho">
                <label className="topico-nome">
                  <input
                    type="checkbox" className="caixa" checked={ligado} disabled={!temDado}
                    aria-label={`incluir ${rotulo} na nota geral`}
                    title={ligado ? 'clique para tirar da nota geral' : 'fora da nota geral: clique para incluir'}
                    onChange={(e) => ligarTopico(topico, e.target.checked)}
                  />
                  <IconeTopico topico={topico} />
                  <span>{rotulo}</span>
                </label>
                <div className="topico-lado">
                  <span className="percentual" title={temDado ? 'peso efetivo na nota geral' : undefined}>
                    {temDado ? `${efetivo(topico) ?? 0}%` : 'sem dados'}
                  </span>
                  {temDado && (
                    <button
                      type="button" className="expandir" aria-expanded={expandido}
                      aria-label={`${expandido ? 'ocultar' : 'ver'} indicadores de ${rotulo}`}
                      title={expandido ? 'ocultar indicadores' : 'ver indicadores'}
                      onClick={() => setAberto(expandido ? null : topico)}
                    >
                      <IconeSeta />
                    </button>
                  )}
                </div>
              </div>
              <div className="trilho">
                <input
                  type="range" min={0} max={100} step={1} value={pesos.topicos[topico]}
                  disabled={!temDado || !ligado} aria-label={`peso de ${rotulo}`}
                  onChange={(e) => mudarTopico(topico, Number(e.target.value))}
                />
                <NumeroPeso
                  rotulo={rotulo} valor={pesos.topicos[topico]} desabilitado={!temDado || !ligado}
                  onChange={(v) => mudarTopico(topico, v)}
                />
              </div>
              {expandido && (
                <div className="indicadores">
                  {Object.keys(cfg.indicadores).map((ind) => {
                    const nome = rotuloIndicador(ind)
                    const valor = pesos.indicadores[topico][ind]
                    const desabilitado = !indicadoresComDado.has(ind) || !ligado
                    return (
                      <div key={ind} className={`indicador ${desabilitado ? 'desabilitado' : ''}`}>
                        <div className="indicador-rotulo">
                          <span>{nome}</span>
                          <NumeroPeso
                            rotulo={nome} valor={valor} desabilitado={desabilitado}
                            onChange={(v) => mudarIndicador(topico, ind, v)}
                          />
                        </div>
                        <div className="trilho">
                          <input
                            type="range" min={0} max={100} step={1} value={valor} disabled={desabilitado}
                            aria-label={`peso de ${nome}`}
                            onChange={(e) => mudarIndicador(topico, ind, Number(e.target.value))}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
        <p className="nota-rodape">
          Os pesos são relativos: o que conta é a proporção entre eles (o % ao lado do nome é o peso efetivo).
          Desmarque um tópico para tirá-lo da nota geral: o peso dele se divide entre os outros na mesma proporção.
          Tópicos sem dados ficam de fora.
        </p>
      </section>
    </aside>
  )
}
