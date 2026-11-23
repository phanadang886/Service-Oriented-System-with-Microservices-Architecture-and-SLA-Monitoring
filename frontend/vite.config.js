import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Cấu hình proxy dev về API Gateway (cổng 80 hoặc 8080)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
