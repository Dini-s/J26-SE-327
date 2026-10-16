/* global process */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The C4 pages read real data from the Python API (python -m apps.api.server, port 8000 by default).
// Override with C4_API=http://127.0.0.1:8001 when the API runs on another port.
const api = process.env.C4_API || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      // changeOrigin stays false on purpose: the API checks that a POST's Origin equals its Host header, so the browser's host must reach it unchanged
      '/api': { target: api, changeOrigin: false },
    },
  },
})
