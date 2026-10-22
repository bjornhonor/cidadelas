import type { FeatureCollection } from 'geojson'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CidadeDetalhada, Dados, Notas, Pesos } from './types'
import { combinarNotas, notasPorIndicador, percentis, pesosIniciais } from './notas'
import { TOPICOS, TOPICOS_CURTOS, formatarNumero } from './rotulos'
import { lerTema, salvarTema, type Tema } from './tema'
import { Controles, type Filtros } from './components/Controles'
import { Mapa } from './components/Mapa'
import { PilulaNota, Ranking, type LinhaRanking } from './components/Ranking'
import { IconeBaixar, IconeLogo, IconeLua, IconeRelogio, IconeSol } from './components/Icones'
import { Detalhe } from './components/Detalhe'
import { Trabalho } from './components/Trabalho'
import {
  carregarDeslocamento, formatarMinutos, lerTrabalho, salvarTrabalho, temposAteTrabalho,
  type Deslocamento, type Trabalho as TipoTrabalho,
} from './deslocamento'

const ESCALA_MINUTOS = 120 // cor do mapa por tempo: satura em 2 h

// Cada visão guarda os seus pesos: os do estado não servem para as zonas de uma cidade
const chavePesos = (slug: string | null) => (slug ? `cidadelas:pesos:${slug}` : 'cidadelas:pesos')

/** "#cidade/valinhos" abre a cidade por dentro; sem hash, o estado. */
function lerSlug(): string | null {
  return /^#cidade\/([a-z0-9-]+)$/.exec(window.location.hash)?.[1] ?? null
}

function lerPesosSalvos(padrao: Pesos, chave: string): Pesos {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave) ?? 'null') as Pesos | null
    if (!salvo) return padrao
    // Mescla com o padrão: indicadores novos no config ganham o peso padrão
    return {
      topicos: { ...padrao.topicos, ...salvo.topicos },
      indicadores: Object.fromEntries(
        Object.entries(padrao.indicadores).map(([t, inds]) => [t, { ...inds, ...salvo.indicadores?.[t] }]),
      ),
      desligados: (salvo.desligados ?? []).filter((t) => t in padrao.topicos),
    }
  } catch {
    return padrao
  }
}

/** Baixa o ranking filtrado em CSV (separado por ponto e vírgula, como o Excel em português espera). */
function exportarCsv(
  linhas: LinhaRanking[], topicos: string[], minutos: (cod: number) => number | null, slug: string | null,
) {
  const comTempo = linhas.some((l) => minutos(l.municipio.cod) != null)
  const numero = (v: number | null) => (v == null ? '' : formatarNumero(v, 1))
  const cabecalho = [
    slug ? 'Posição entre as zonas' : 'Posição no estado', slug ? 'Zona' : 'Município', 'População', 'Região', ...(comTempo ? ['Minutos até o trabalho'] : []),
    'Nota geral', ...topicos.map((t) => TOPICOS[t] ?? t),
  ]
  const corpo = linhas.map(({ posicaoEstado, municipio: m, notas }) => [
    String(posicaoEstado), m.nome, String(m.populacao), m.regiao_intermediaria,
    ...(comTempo ? [numero(minutos(m.cod))] : []),
    numero(notas.geral), ...topicos.map((t) => numero(notas.topicos[t])),
  ])
  const celula = (c: string) => (/[;"\n]/.test(c) ? `"${c.replaceAll('"', '""')}"` : c)
  const texto = [cabecalho, ...corpo].map((linha) => linha.map(celula).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿' + texto], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = slug ? `cidadelas-${slug}-zonas.csv` : 'cidadelas-ranking.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function salvarPesos(p: Pesos, chave: string) {
  try {
    localStorage.setItem(chave, JSON.stringify(p))
  } catch {
    // navegação privada ou armazenamento bloqueado: os pesos valem só nesta sessão
  }
}

export default function App() {
  const [slug, setSlug] = useState(lerSlug)
  const [carregado, setCarregado] = useState<{ slug: string | null; dados: Dados; malha: FeatureCollection } | null>(null)
  const [cidades, setCidades] = useState<CidadeDetalhada[]>([])
  const [erro, setErro] = useState<{ slug: string | null; texto: string } | null>(null) // do carregamento de qual visão

  useEffect(() => {
    const mudou = () => setSlug(lerSlug())
    window.addEventListener('hashchange', mudou)
    return () => window.removeEventListener('hashchange', mudou)
  }, [])

  useEffect(() => {
    // Opcional: sem nenhuma cidade calculada, o app só não mostra o "ver por dentro"
    fetch('/data/cidades/index.json').then((r) => r.json()).then(setCidades).catch(() => setCidades([]))
  }, [])

  useEffect(() => {
    let cancelado = false
    const [arquivo, contorno, comando] = slug
      ? [`/data/cidades/${slug}.json`, `/data/cidades/${slug}.geojson`, `python -m cidadelas cidade ${slug}`]
      : ['/data/cidadelas.json', '/data/malha_sp.geojson', 'python -m cidadelas calcular']
    Promise.all([fetch(arquivo).then((r) => r.json()), fetch(contorno).then((r) => r.json())])
      .then(([dados, malha]) => {
        if (!cancelado) setCarregado({ slug, dados, malha })
      })
      .catch(() => {
        if (!cancelado) setErro({ slug, texto: `Não encontrei os dados. Rode \`${comando}\` na raiz do projeto.` })
      })
    return () => {
      cancelado = true
    }
  }, [slug])

  if (erro?.slug === slug) return <p className="aviso">{erro.texto}</p>
  if (!carregado || carregado.slug !== slug) return <p className="aviso">Carregando…</p>
  return <Painel key={slug ?? 'estado'} slug={slug} dados={carregado.dados} malha={carregado.malha} cidades={cidades} />
}

function Painel({ slug, dados, malha, cidades }: {
  slug: string | null
  dados: Dados
  malha: FeatureCollection
  cidades: CidadeDetalhada[]
}) {
  const { config, municipios } = dados
  const cidade = dados.cidade ?? null // dentro de uma cidade, cada "município" é uma zona
  const chave = chavePesos(slug)
  const padrao = useMemo(() => pesosIniciais(config), [config])
  const [pesos, setPesos] = useState(() => lerPesosSalvos(padrao, chave))
  const [filtros, setFiltros] = useState<Filtros>({ populacaoMin: 0, regiao: '', busca: '', tempoMax: 0 })
  const [corPor, setCorPor] = useState('geral')
  const [selecionado, setSelecionado] = useState<number | null>(null)
  const [trabalho, setTrabalho] = useState<TipoTrabalho>(lerTrabalho)
  const [marcando, setMarcando] = useState(false)
  const [deslocamento, setDeslocamento] = useState<Deslocamento | 'erro' | null>(null)
  const [tema, setTema] = useState<Tema>(lerTema)
  const pedido = useRef<Promise<void> | null>(null)

  const mudarPesos = (p: Pesos) => {
    setPesos(p)
    salvarPesos(p, chave)
  }
  const mudarTema = (t: Tema) => {
    salvarTema(t) // antes do render: o mapa troca as cores logo em seguida
    setTema(t)
  }
  const mudarTrabalho = (t: TipoTrabalho) => {
    setTrabalho(t)
    salvarTrabalho(t)
  }

  // A matriz de tempos (~2,6 MB) só é baixada quando há local de trabalho
  // O tempo até o trabalho é por município: dentro de uma cidade ele não separa as zonas
  const local = trabalho.modo === 'presencial' && !cidade ? trabalho.local : null
  const precisaDeslocamento = local != null
  useEffect(() => {
    if (!precisaDeslocamento || pedido.current) return
    pedido.current = carregarDeslocamento().then(setDeslocamento).catch(() => setDeslocamento('erro'))
  }, [precisaDeslocamento])

  const deslocamentoPronto = deslocamento === 'erro' ? null : deslocamento
  const ateTrabalho = useMemo(
    () => (local && deslocamentoPronto ? temposAteTrabalho(deslocamentoPronto, local.lat, local.lon) : null),
    [local, deslocamentoPronto],
  )
  const tempos = ateTrabalho?.tempos ?? null
  // No modo remoto, a cor e o filtro por tempo saem de cena sem perder a escolha
  const corEfetiva = corPor === 'trabalho' && !tempos ? 'geral' : corPor
  const tempoMax = tempos ? filtros.tempoMax : 0

  const porIndicador = useMemo(() => notasPorIndicador(municipios, config), [municipios, config])
  const notas = useMemo(
    () => new Map<number, Notas>(municipios.map((m) => [m.cod, combinarNotas(porIndicador.get(m.cod)!, config, pesos)])),
    [municipios, porIndicador, config, pesos],
  )

  const indicadoresComDado = useMemo(
    () => new Set(municipios.flatMap((m) => Object.keys(m.indicadores))),
    [municipios],
  )
  const topicosComDado = useMemo(
    () => new Set(Object.entries(config.topicos)
      .filter(([, c]) => Object.keys(c.indicadores).some((i) => indicadoresComDado.has(i)))
      .map(([t]) => t)),
    [config, indicadoresComDado],
  )
  const regioes = useMemo(() => [...new Set(municipios.map((m) => m.regiao_intermediaria))].sort(), [municipios])

  const busca = filtros.busca.trim().toLocaleLowerCase('pt-BR')
  const visiveis = useMemo(() => new Set(municipios
    .filter((m) => m.populacao >= filtros.populacaoMin)
    .filter((m) => !filtros.regiao || m.regiao_intermediaria === filtros.regiao)
    .filter((m) => !busca || [m.nome, ...(m.bairros ?? [])].some((n) => n.toLocaleLowerCase('pt-BR').includes(busca)))
    .filter((m) => !tempoMax || (tempos?.get(m.cod)?.minutos ?? Infinity) <= tempoMax)
    .map((m) => m.cod)), [municipios, filtros.populacaoMin, filtros.regiao, busca, tempoMax, tempos])

  // Posição entre todos (o estado ou todas as zonas): buscar ou filtrar não muda a posição de ninguém
  const posicoesEstado = useMemo(() => new Map([...municipios]
    .sort((a, b) => (notas.get(b.cod)!.geral ?? -1) - (notas.get(a.cod)!.geral ?? -1))
    .map((m, i) => [m.cod, i + 1])), [municipios, notas])

  const linhas: LinhaRanking[] = useMemo(() => municipios
    .filter((m) => visiveis.has(m.cod))
    .map((m) => ({ municipio: m, notas: notas.get(m.cod)!, posicao: 0, posicaoEstado: posicoesEstado.get(m.cod)! }))
    .sort((a, b) => a.posicaoEstado - b.posicaoEstado)
    .map((l, i) => ({ ...l, posicao: i + 1 })), [municipios, visiveis, notas, posicoesEstado])

  // Colorir pelo tempo: 0 min = 100 (mais escuro) até 2 h ou mais = 0, na mesma rampa das notas
  const notasMapa = useMemo(
    () => corEfetiva === 'trabalho' && tempos
      ? new Map(municipios.map((m) => {
        const t = tempos.get(m.cod)?.minutos
        return [m.cod, t == null ? null : 100 * (1 - Math.min(t, ESCALA_MINUTOS) / ESCALA_MINUTOS)]
      }))
      : new Map([...notas].map(([cod, n]) => [cod, corEfetiva === 'geral' ? n.geral : n.topicos[corEfetiva]])),
    [notas, corEfetiva, tempos, municipios],
  )
  // Notas: a cor vai pela posição (percentil), e a legenda mostra a nota da pior, da mediana e da melhor.
  // O tempo até o trabalho fica na escala própria, em minutos
  const coresMapa = useMemo(
    () => (corEfetiva === 'trabalho' ? notasMapa : percentis(notasMapa)),
    [corEfetiva, notasMapa],
  )
  const legendaMapa = useMemo((): [string, string, string] => {
    if (corEfetiva === 'trabalho') return [`${ESCALA_MINUTOS / 60} h ou mais`, `${ESCALA_MINUTOS / 120} h`, '0 min']
    const valores = [...notasMapa.values()].filter((v): v is number => v != null).sort((a, b) => a - b)
    if (!valores.length) return ['pior', '', 'melhor']
    const meio = valores.length / 2
    const mediana = valores.length % 2 ? valores[Math.floor(meio)] : (valores[meio - 1] + valores[meio]) / 2
    return [`${formatarNumero(valores[0])} · pior`, `${formatarNumero(mediana)} mediana`, `${formatarNumero(valores.at(-1)!)} · melhor`]
  }, [corEfetiva, notasMapa])

  const topicosVisiveis = [...topicosComDado]
  const municipioSelecionado = selecionado != null ? municipios.find((m) => m.cod === selecionado) : undefined
  const posicaoNoFiltro = linhas.find((l) => l.municipio.cod === selecionado)?.posicao ?? null
  const filtrando = linhas.length < municipios.length
  const rotuloCor = corEfetiva === 'geral' ? 'Nota geral' : corEfetiva === 'trabalho' ? 'Tempo até o trabalho' : TOPICOS[corEfetiva]
  const textoTempo = (cod: number) => {
    const t = tempos?.get(cod)
    return t ? formatarMinutos(t.minutos) : null
  }
  const estadoDeslocamento = !local ? null : deslocamento === 'erro' ? 'erro' : deslocamentoPronto ? 'ok' : 'carregando'
  const porCod = new Map(municipios.map((m) => [m.cod, m]))

  // Cartão do mapa ao passar o mouse: posição, nota da cor atual, tempo até o trabalho e três tópicos
  const tooltip = (cod: number) => {
    const m = porCod.get(cod)!
    const n = notas.get(cod)!
    const posicao = posicoesEstado.get(cod)!
    const tempo = textoTempo(cod)
    return (
      <>
        <div className="tooltip-topo">
          <div>
            <span className={`tooltip-posicao ${visiveis.has(cod) ? '' : 'fora'}`}>
              {posicao}º de {municipios.length}{visiveis.has(cod) ? '' : ' · fora do filtro'}
            </span>
            <h4>{m.nome}</h4>
          </div>
          <div className="tooltip-nota">
            {corEfetiva === 'trabalho' ? (
              <span className="pilula-nota">{tempo ?? 'sem rota'}</span>
            ) : (
              <PilulaNota valor={notasMapa.get(cod) ?? null} posicao={posicao} />
            )}
            <small>{rotuloCor.toLowerCase()}</small>
          </div>
        </div>
        {tempo && corEfetiva !== 'trabalho' && (
          <div className="tooltip-extra"><IconeRelogio /> {tempo} até o trabalho</div>
        )}
        <div className="tooltip-topicos">
          {topicosVisiveis.filter((t) => t !== corEfetiva).slice(0, 3).map((t) => (
            <div key={t}>
              <span>{TOPICOS_CURTOS[t] ?? t}</span>
              <strong>{n.topicos[t] != null ? formatarNumero(n.topicos[t]!, 1) : '–'}</strong>
            </div>
          ))}
        </div>
      </>
    )
  }

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <div className="logo">
            <span className="logo-icone"><IconeLogo /></span>
            <h1>Cidadelas</h1>
          </div>
          <span className="divisor" />
          <div className="meta-dados">
            <span className="pulso" />
            <span>
              {cidade ? `${cidade.nome} por dentro: ${municipios.length} zonas` : `${municipios.length} municípios de SP`}
              {' '}· {dados.coletas.length} fontes integradas · calculado em{' '}
              {new Date(`${dados.gerado_em}T12:00`).toLocaleDateString('pt-BR')}
            </span>
          </div>
          {cidade && <a className="link voltar-estado" href="#">← todos os municípios</a>}
        </div>
        <div className="acoes">
          <details className="fontes">
            <summary>Fontes de dados</summary>
            <ul className="fontes-lista">
              {dados.coletas.map((c) => (
                <li key={c.fonte}><strong>{c.fonte}</strong><span>{c.referencia}</span></li>
              ))}
            </ul>
          </details>
          <span className="divisor" />
          <div className="pilula-tema" role="radiogroup" aria-label="Tema">
            <button type="button" role="radio" aria-checked={tema === 'claro'} onClick={() => mudarTema('claro')}>
              <IconeSol /> Claro
            </button>
            <button type="button" role="radio" aria-checked={tema === 'escuro'} onClick={() => mudarTema('escuro')}>
              <IconeLua /> Escuro
            </button>
          </div>
          <button
            type="button" className="botao-primario" disabled={!linhas.length}
            title="Baixar o ranking filtrado em CSV"
            onClick={() => exportarCsv(linhas, topicosVisiveis, (cod) => tempos?.get(cod)?.minutos ?? null, slug)}
          >
            <IconeBaixar /> Exportar
          </button>
        </div>
      </header>

      <Controles
        cidade={cidade?.nome ?? null}
        trabalho={cidade ? null : (
          <Trabalho
            trabalho={trabalho}
            tempoMax={filtros.tempoMax}
            marcando={marcando}
            estado={estadoDeslocamento}
            kmAtePonto={ateTrabalho?.kmAtePonto ?? null}
            onTrabalho={mudarTrabalho}
            onTempoMax={(minutos) => setFiltros({ ...filtros, tempoMax: minutos })}
            onMarcando={setMarcando}
          />
        )}
        config={config}
        pesos={pesos}
        topicosComDado={topicosComDado}
        indicadoresComDado={indicadoresComDado}
        regioes={regioes}
        filtros={filtros}
        aptas={linhas.length}
        total={municipios.length}
        onPesos={mudarPesos}
        onFiltros={setFiltros}
        onRestaurarPesos={() => mudarPesos(padrao)}
      />

      <main>
        <div className="barra-mapa">
          <label className="colorir flutuante">
            <span>Colorir por:</span>
            <select value={corEfetiva} onChange={(e) => setCorPor(e.target.value)}>
              <option value="geral">Nota geral</option>
              {topicosVisiveis.map((t) => <option key={t} value={t}>{TOPICOS[t] ?? t}</option>)}
              {tempos && <option value="trabalho">Tempo até o trabalho</option>}
            </select>
          </label>
          <span className="no-filtro">{linhas.length} {cidade ? 'zonas' : 'cidades'} no filtro</span>
          {marcando && <span className="marcando-aviso">Clique no mapa onde fica o trabalho</span>}
        </div>
        <Mapa
          malha={malha}
          cores={coresMapa}
          visiveis={visiveis}
          selecionado={selecionado}
          tema={tema}
          tooltip={tooltip}
          rotuloNota={rotuloCor}
          legenda={legendaMapa}
          subtituloLegenda={corEfetiva === 'trabalho' ? undefined : 'cor pela posição'}
          trabalho={local}
          marcando={marcando}
          onMarcar={(lat, lon) => {
            mudarTrabalho({ modo: 'presencial', local: { lat, lon, rotulo: `ponto marcado no mapa` } })
            setMarcando(false)
          }}
          onSelecionar={setSelecionado}
        />
      </main>

      <section className="lateral">
        {municipioSelecionado ? (
          <Detalhe
            municipio={municipioSelecionado}
            notas={notas.get(municipioSelecionado.cod)!}
            posicao={posicoesEstado.get(municipioSelecionado.cod)!}
            total={municipios.length}
            posicaoNoFiltro={filtrando ? posicaoNoFiltro : undefined}
            config={config}
            unidades={dados.unidades}
            tempo={tempos?.get(municipioSelecionado.cod) ?? null}
            anosCrime={cidade?.anos_crime ?? 5}
            zona={cidade != null}
            porDentro={cidade ? null : cidades.find((c) => c.cod === municipioSelecionado.cod)?.slug ?? null}
            onFechar={() => setSelecionado(null)}
          />
        ) : (
          <Ranking
            linhas={linhas} topicos={topicosVisiveis} tempos={tempos} cidade={cidade?.nome ?? null}
            selecionado={selecionado} onSelecionar={setSelecionado}
          />
        )}
      </section>
    </div>
  )
}
