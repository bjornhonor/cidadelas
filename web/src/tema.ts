// Tema claro/escuro: começa no escuro (o visual de referência) e, depois de escolhido no botão, fica guardado

export type Tema = 'claro' | 'escuro'

const CHAVE = 'cidadelas:tema'

export function lerTema(): Tema {
  try {
    const salvo = localStorage.getItem(CHAVE)
    if (salvo === 'claro' || salvo === 'escuro') return salvo
  } catch {
    // armazenamento bloqueado: fica no padrão
  }
  return 'escuro'
}

/** Aplica no <html> já na hora: o mapa lê as cores do tema logo ao ser criado. */
export function aplicarTema(tema: Tema) {
  document.documentElement.dataset.theme = tema === 'escuro' ? 'dark' : 'light'
}

export function salvarTema(tema: Tema) {
  aplicarTema(tema)
  try {
    localStorage.setItem(CHAVE, tema)
  } catch {
    // vale só nesta sessão
  }
}
