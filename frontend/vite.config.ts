import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server binds 0.0.0.0 and proxies /api to the FastAPI backend so the
// browser never needs to reach the backend directly.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
