import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// proxy /api → FastAPI (localhost:8000) กัน CORS ตอน dev
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
      // Phase 4: รูปหลักฐานจริงเสิร์ฟจาก FastAPI StaticFiles
      '/uploads': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      // Phase 5: WebSocket realtime
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
