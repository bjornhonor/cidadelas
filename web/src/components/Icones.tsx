// Ícones de traço (24×24, cor do texto), no estilo do layout do Stitch

const PROPS = {
  className: 'icone', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true,
} as const

export const IconeLogo = () => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M7 26H25M9 26V13L16 6L23 13V26M13 26V19C13 17.34 14.34 16 16 16C17.66 16 19 17.34 19 19V26M11 11H13M19 11H21" />
  </svg>
)

export const IconePino = () => (
  <svg {...PROPS}>
    <path d="M17.66 16.66 13.41 20.9a2 2 0 0 1-2.83 0l-4.24-4.24a8 8 0 1 1 11.32 0z" />
    <path d="M15 11a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />
  </svg>
)

export const IconeLupa = () => (
  <svg {...PROPS}><path d="m21 21-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" /></svg>
)

export const IconeRelogio = () => (
  <svg {...PROPS} style={{ width: 12, height: 12 }}><path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" /></svg>
)

export const IconeSol = () => (
  <svg {...PROPS} strokeWidth={1.8}>
    <circle cx="12" cy="12" r="5" />
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
)

export const IconeLua = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
    <path d="M17.29 13.29A8 8 0 0 1 6.71 2.71a8 8 0 1 0 10.58 10.58z" />
  </svg>
)

export const IconeBaixar = () => (
  <svg {...PROPS}><path d="M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1m-4-4-4 4m0 0-4-4m4 4V4" /></svg>
)

export const IconeSeta = () => (
  <svg {...PROPS}><path d="m19 9-7 7-7-7" /></svg>
)

const TOPICOS: Record<string, string> = {
  // escudo com visto
  seguranca: 'M9 12l2 2 4-4m5.62-4.02A11.96 11.96 0 0 1 12 2.94a11.96 11.96 0 0 1-8.62 3.04A12.02 12.02 0 0 0 3 9c0 5.59 3.82 10.29 9 11.62 5.18-1.33 9-6.03 9-11.62 0-1.04-.13-2.05-.38-3.02z',
  // coração
  saude: 'M4.32 6.32a4.5 4.5 0 0 0 0 6.36L12 20.36l7.68-7.68a4.5 4.5 0 0 0-6.36-6.36L12 7.64l-1.32-1.32a4.5 4.5 0 0 0-6.36 0z',
  // cartão
  custo: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 0 0 3-3V8a3 3 0 0 0-3-3H6a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3z',
  // prédio
  infraestrutura: 'M19 21V5a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5m-4 0h4',
  // folha
  natureza: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10zM2 21c0-3 1.85-5.36 5.08-6',
}

export const IconeTopico = ({ topico }: { topico: string }) => (
  <svg {...PROPS}><path d={TOPICOS[topico] ?? 'M12 6v12M6 12h12'} /></svg>
)
