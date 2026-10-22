import type { FeatureCollection } from 'geojson'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  Map as MapaLibre, Marker, NavigationControl, setWorkerUrl,
  type ExpressionSpecification, type MapLayerMouseEvent, type MapMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { LocalTrabalho } from '../deslocamento'
import type { Tema } from '../tema'

// No build, o caminho relativo que o MapLibre usa para achar o worker não sobrevive ao bundle.
// Em dev ele funciona sozinho (maplibre-gl fica fora do optimizeDeps).
if (import.meta.env.PROD) {
  const { default: workerUrl } = await import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')
  setWorkerUrl(workerUrl)
}

// Rampa sequencial em menta: no escuro a nota alta acende; no claro a nota alta escurece. Mesmas cores de --rampa
const CORES: Record<Tema, { rampa: string[]; semDado: string; contorno: string; destaque: string }> = {
  escuro: {
    rampa: ['#232927', '#2a4a42', '#2f7a67', '#3fb898', '#66f4c8'],
    semDado: '#1a1e1d',
    contorno: '#252b29',
    destaque: '#ffffff',
  },
  claro: {
    rampa: ['#e4f1ec', '#a9dccb', '#4cbf9d', '#138a6c', '#0b4f40'],
    semDado: '#e6e9e7',
    contorno: '#ffffff',
    destaque: '#111313',
  },
}

function corPreenchimento(tema: Tema) {
  const { rampa, semDado } = CORES[tema]
  return [
    'case',
    ['!', ['boolean', ['feature-state', 'visivel'], true]], semDado,
    ['==', ['typeof', ['feature-state', 'nota']], 'number'],
    ['interpolate', ['linear'], ['feature-state', 'nota'], ...rampa.flatMap((cor, i) => [i * 25, cor])],
    semDado,
  ] as ExpressionSpecification
}

const LARGURA_TOOLTIP = 232

/** Caixa que contém a malha toda: o mapa abre enquadrado no estado ou na cidade. */
function limites(malha: FeatureCollection): [[number, number], [number, number]] {
  let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity]
  const visitar = (c: unknown): void => {
    if (typeof (c as number[])[0] === 'number') {
      const [x, y] = c as number[]
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y)
    } else (c as unknown[]).forEach(visitar)
  }
  for (const f of malha.features) if (f.geometry.type !== 'GeometryCollection') visitar(f.geometry.coordinates)
  return [[x0, y0], [x1, y1]]
}

interface Props {
  malha: FeatureCollection
  cores: Map<number, number | null> // 0..100 na rampa (com nota, é o percentil, não a nota)
  visiveis: Set<number>
  selecionado: number | null
  tema: Tema
  tooltip: (cod: number) => ReactNode // conteúdo do cartão ao passar o mouse
  rotuloNota: string // título da legenda
  legenda: [string, string, string] // rótulos do começo, do meio e do fim da escala
  subtituloLegenda?: string
  trabalho: LocalTrabalho | null
  marcando: boolean // o próximo clique marca o local de trabalho em vez de selecionar a cidade
  onMarcar: (lat: number, lon: number) => void
  onSelecionar: (cod: number) => void
}

export function Mapa(props: Props) {
  const { malha, cores, visiveis, selecionado, tema, tooltip, rotuloNota, legenda, subtituloLegenda, trabalho, marcando } = props
  const container = useRef<HTMLDivElement>(null)
  const mapa = useRef<MapaLibre | null>(null)
  const alfinete = useRef<Marker | null>(null)
  const [pronto, setPronto] = useState(false)
  // largura e altura do mapa no momento do movimento: o cartão vira de lado perto das bordas
  const [hover, setHover] = useState<{ cod: number; x: number; y: number; w: number; h: number } | null>(null)
  // O mapa é criado uma vez; as refs deixam os eventos sempre lerem a versão atual das props
  const atual = useRef(props)
  useEffect(() => {
    atual.current = props
  })

  useEffect(() => {
    const cores = CORES[atual.current.tema]
    const m = new MapaLibre({
      container: container.current!,
      style: {
        version: 8,
        sources: { municipios: { type: 'geojson', data: malha, promoteId: 'cod' } },
        // Sem camada de fundo: o canvas fica transparente e mostra a grade de pontos do CSS
        layers: [
          {
            id: 'preenchimento',
            type: 'fill',
            source: 'municipios',
            paint: { 'fill-color': corPreenchimento(atual.current.tema) },
          },
          {
            id: 'contorno',
            type: 'line',
            source: 'municipios',
            paint: { 'line-color': cores.contorno, 'line-width': 0.6 },
          },
          {
            id: 'destaque',
            type: 'line',
            source: 'municipios',
            paint: {
              'line-color': cores.destaque,
              'line-width': ['case', ['boolean', ['feature-state', 'selecionado'], false], 2.5, 0],
            },
          },
        ],
      },
      bounds: limites(malha),
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
    })
    m.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    m.on('load', () => setPronto(true))
    m.on('mousemove', 'preenchimento', (e: MapLayerMouseEvent) => {
      const cod = e.features?.[0]?.id as number | undefined
      m.getCanvas().style.cursor = atual.current.marcando ? 'crosshair' : cod ? 'pointer' : ''
      const { clientWidth: w, clientHeight: h } = m.getContainer()
      setHover(cod ? { cod, x: e.point.x, y: e.point.y, w, h } : null)
    })
    m.on('mouseleave', 'preenchimento', () => {
      m.getCanvas().style.cursor = atual.current.marcando ? 'crosshair' : ''
      setHover(null)
    })
    m.on('click', (e: MapMouseEvent) => {
      if (atual.current.marcando) {
        atual.current.onMarcar(e.lngLat.lat, e.lngLat.lng)
        return
      }
      const cod = m.queryRenderedFeatures(e.point, { layers: ['preenchimento'] })[0]?.id as number | undefined
      if (cod) atual.current.onSelecionar(cod)
    })
    m.on('error', (e) => console.error('MapLibre:', e.error))
    mapa.current = m
    if (import.meta.env.DEV) (window as unknown as { __mapa: MapaLibre }).__mapa = m
    return () => m.remove()
  }, [malha])

  useEffect(() => {
    if (!pronto || !mapa.current) return
    for (const f of malha.features) {
      const cod = f.properties!.cod as number
      mapa.current.setFeatureState(
        { source: 'municipios', id: cod },
        { nota: cores.get(cod) ?? null, visivel: visiveis.has(cod), selecionado: cod === selecionado },
      )
    }
  }, [pronto, malha, cores, visiveis, selecionado])

  useEffect(() => {
    if (!pronto || !mapa.current) return
    const cores = CORES[tema]
    mapa.current.setPaintProperty('preenchimento', 'fill-color', corPreenchimento(tema))
    mapa.current.setPaintProperty('contorno', 'line-color', cores.contorno)
    mapa.current.setPaintProperty('destaque', 'line-color', cores.destaque)
  }, [pronto, tema])

  useEffect(() => {
    if (mapa.current) mapa.current.getCanvas().style.cursor = marcando ? 'crosshair' : ''
  }, [marcando])

  // Alfinete do trabalho: arrastável para ajustar o local sem buscar de novo
  useEffect(() => {
    if (!pronto || !mapa.current) return
    if (!trabalho) {
      alfinete.current?.remove()
      alfinete.current = null
      return
    }
    if (!alfinete.current) {
      const elemento = document.createElement('div')
      elemento.className = 'alfinete-trabalho'
      elemento.title = 'Trabalho (arraste para mudar)'
      alfinete.current = new Marker({ element: elemento, draggable: true, anchor: 'bottom' })
        .setLngLat([trabalho.lon, trabalho.lat])
        .addTo(mapa.current)
      alfinete.current.on('dragend', () => {
        const { lat, lng } = alfinete.current!.getLngLat()
        atual.current.onMarcar(lat, lng)
      })
    } else {
      alfinete.current.setLngLat([trabalho.lon, trabalho.lat])
    }
  }, [pronto, trabalho])

  const posicaoTooltip = hover && {
    left: hover.x + 16 + LARGURA_TOOLTIP > hover.w ? hover.x - 16 - LARGURA_TOOLTIP : hover.x + 16,
    top: hover.y + 180 > hover.h ? Math.max(hover.y - 180, 8) : hover.y + 16,
  }
  return (
    <div className="mapa">
      <div ref={container} className="mapa-canvas" />
      {!pronto && <p className="mapa-carregando muted">Carregando mapa…</p>}
      {hover && posicaoTooltip && (
        <div className="tooltip flutuante" style={posicaoTooltip}>{tooltip(hover.cod)}</div>
      )}
      <div className="legenda flutuante" aria-label={`Escala de ${rotuloNota}`}>
        <div className="legenda-titulo">
          <span>{rotuloNota}</span>
          {subtituloLegenda && <small>{subtituloLegenda}</small>}
        </div>
        <div className="legenda-barra" />
        <div className="legenda-rotulos">
          {legenda.map((r, i) => <span key={i}>{r}</span>)}
        </div>
      </div>
    </div>
  )
}
