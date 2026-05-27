/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  base: '/app/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/candidates': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/candidate': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/demo': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/events': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/scoring-context': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/state': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/timeline': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
