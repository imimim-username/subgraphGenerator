import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend API port during development.
// Run the FastAPI server on this port:
//   uvicorn subgraph_wizard.server:app --port 8000 --reload
// Then `npm run dev` here — Vite (5173) proxies /api/* to the backend.
const API_PORT = parseInt(process.env.VITE_API_PORT ?? '8000', 10)

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy /api calls to the FastAPI backend during development.
    // Override the backend port with VITE_API_PORT env var if needed.
    proxy: {
      '/api': {
        target: `http://localhost:${API_PORT}`,
        changeOrigin: true,
      },
    },
  },
  // Pre-built bundle output: shipped inside the Python package.
  // End users running `subgraph-wizard --ui` don't need Node.js.
  build: {
    outDir: '../src/subgraph_wizard/static',
    emptyOutDir: true,
  },
})
