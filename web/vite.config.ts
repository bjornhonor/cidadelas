import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' }, // o worker do MapLibre é um módulo ES
  // Pré-empacotado, o MapLibre 6 perde o caminho relativo até o próprio worker
  optimizeDeps: { exclude: ['maplibre-gl'] },
})
