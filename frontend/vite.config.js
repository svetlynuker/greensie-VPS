import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Ve vývoji přeposílá /api na běžící backend (uvicorn na portu 8000),
  // aby frontend volal API stejně jako v produkci (přes Caddy).
  // VITE_API_TARGET umí cíl přesměrovat — díky tomu může vedle běžné instance
  // běžet druhá (např. náhled z jiné větve na jiném portu).
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
