import { useState } from 'react'
import type { LocalTrabalho, Trabalho as TipoTrabalho } from '../deslocamento'
import { IconePino } from './Icones'

const LIMITES_MINUTOS = [0, 15, 20, 30, 45, 60, 90, 120]

interface Props {
  trabalho: TipoTrabalho
  tempoMax: number
  marcando: boolean
  estado: 'carregando' | 'erro' | 'ok' | null
  kmAtePonto: number | null
  onTrabalho: (t: TipoTrabalho) => void
  onTempoMax: (minutos: number) => void
  onMarcando: (marcando: boolean) => void
}

/** Busca no Nominatim (OpenStreetMap). O texto digitado vai para o servidor deles; nada mais sai do navegador. */
async function buscarEndereco(texto: string): Promise<LocalTrabalho[]> {
  const params = new URLSearchParams({
    q: texto, format: 'jsonv2', limit: '8', countrycodes: 'br', 'accept-language': 'pt-BR',
    viewbox: '-53.2,-19.7,-44.1,-25.4', bounded: '1', // só o estado de SP
  })
  const r = await fetch(`https://nominatim.openstreetmap.org/search?${params}`)
  if (!r.ok) throw new Error(String(r.status))
  const itens = (await r.json()) as { display_name: string; lat: string; lon: string }[]
  const locais = itens.map((i) => ({
    // "Avenida Paulista, Bela Vista, São Paulo, Região Imediata..., Brasil": as três primeiras partes bastam
    rotulo: i.display_name.split(', ').slice(0, 3).join(', '),
    lat: Number(i.lat),
    lon: Number(i.lon),
  }))
  // Uma avenida vem em vários trechos com o mesmo nome: fica o primeiro (o mais relevante para o Nominatim)
  return locais.filter((l, i) => locais.findIndex((o) => o.rotulo === l.rotulo) === i)
}

export function Trabalho({ trabalho, tempoMax, marcando, estado, kmAtePonto, onTrabalho, onTempoMax, onMarcando }: Props) {
  const [texto, setTexto] = useState('')
  const [resultados, setResultados] = useState<LocalTrabalho[] | null>(null)
  const [buscando, setBuscando] = useState(false)
  const [erroBusca, setErroBusca] = useState(false)
  const { modo, local } = trabalho

  const buscar = async () => {
    setBuscando(true)
    setErroBusca(false)
    try {
      setResultados(await buscarEndereco(texto.trim()))
    } catch {
      setErroBusca(true)
      setResultados(null)
    } finally {
      setBuscando(false)
    }
  }

  const escolher = (l: LocalTrabalho) => {
    onTrabalho({ modo: 'presencial', local: l })
    setResultados(null)
    setTexto('')
  }

  const tempoAtivo = modo === 'presencial' && local != null && estado === 'ok'

  return (
    <section className="cartao">
      <div className="cartao-titulo">
        <h2>Modelo de trabalho</h2>
        {tempoAtivo && <span className="selo">Tempo ativo</span>}
      </div>
      <div className="segmentado" role="radiogroup" aria-label="Como você trabalha">
        {(['remoto', 'presencial'] as const).map((m) => (
          <button
            key={m} type="button" role="radio" aria-checked={modo === m}
            onClick={() => {
              if (m === 'remoto') onMarcando(false)
              onTrabalho({ ...trabalho, modo: m })
            }}
          >
            {m === 'remoto' ? 'Remoto' : 'Presencial'}
          </button>
        ))}
      </div>

      {modo === 'remoto' && (
        <p className="nota-rodape">Sem deslocamento: o ranking não leva o trabalho em conta.</p>
      )}

      {modo === 'presencial' && (
        <>
          <div className="campo">
            <div className="campo-rotulo">
              <span>Endereço do trabalho</span>
              <button type="button" className="link" onClick={() => onMarcando(!marcando)}>
                {marcando ? 'cancelar' : 'marcar no mapa'}
              </button>
            </div>
            <form
              className="com-icone"
              onSubmit={(e) => {
                e.preventDefault()
                if (texto.trim()) void buscar()
              }}
            >
              <IconePino />
              <input
                type="search" className="entrada com-botao" value={texto} aria-label="Endereço do trabalho"
                placeholder={local ? 'trocar endereço' : 'ex.: Av. Paulista, 1000, São Paulo'}
                onChange={(e) => setTexto(e.target.value)}
              />
              <button type="submit" className="botao-interno" disabled={buscando || !texto.trim()}>
                {buscando ? '…' : 'Buscar'}
              </button>
            </form>
            {local && (
              <p className="local-atual" title="Arraste o alfinete no mapa para ajustar">
                <IconePino />
                {local.rotulo}
              </p>
            )}
          </div>
          {marcando && <p className="nota-rodape">Clique no mapa onde fica o trabalho.</p>}
          {erroBusca && <p className="nota-rodape">A busca de endereço falhou. Tente de novo ou marque no mapa.</p>}
          {resultados && (
            resultados.length ? (
              <ul className="resultados-endereco">
                {resultados.map((r) => (
                  <li key={`${r.lat},${r.lon}`}>
                    <button type="button" onClick={() => escolher(r)}>{r.rotulo}</button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="nota-rodape">Nada encontrado em SP. Tente rua e cidade, ou marque no mapa.</p>
            )
          )}

          {local && (
            <div className="campo">
              <label className="campo-rotulo" htmlFor="tempo-max">
                <span>Tempo máximo de trajeto</span>
                <strong>{tempoMax ? `até ${tempoMax} min` : 'qualquer'}</strong>
              </label>
              <select
                id="tempo-max" className="seletor" value={tempoMax}
                onChange={(e) => onTempoMax(Number(e.target.value))}
              >
                {LIMITES_MINUTOS.map((m) => (
                  <option key={m} value={m}>{m === 0 ? 'Sem limite de deslocamento' : `até ${m} min`}</option>
                ))}
              </select>
              {estado === 'carregando' && <p className="nota-rodape">Calculando os tempos…</p>}
              {estado === 'erro' && (
                <p className="nota-rodape">
                  Não encontrei os tempos de carro. Rode `python -m cidadelas coletar deslocamento` e depois `calcular`.
                </p>
              )}
              {estado === 'ok' && kmAtePonto != null && kmAtePonto > 10 && (
                <p className="nota-rodape">
                  O local fica a {Math.round(kmAtePonto)} km da área habitada mais próxima: os tempos são aproximados.
                </p>
              )}
              <p className="nota-rodape">
                * Carro em via livre, sem trânsito: na hora do rush, sobretudo na Grande SP, conte com bem mais. O
                tempo de cada cidade é a média de onde a população dela mora.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  )
}
