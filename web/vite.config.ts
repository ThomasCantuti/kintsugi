import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// dev: `npm run dev` on :5173, API and SSE proxied to `uv run python -m kintsugi` on :8000.
// prod: `npm run build` → web/dist, served by FastAPI (committed, so the Python run needs no Node).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
