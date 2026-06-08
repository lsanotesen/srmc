import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://srmc-backend:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://srmc-backend:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
