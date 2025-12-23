import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // Use relative asset URLs by default so the SPA can run under any proxy prefix.
  // If you need an absolute base, set VITE_BASE_PATH (Vite expects a trailing slash).
  const base =
    env.VITE_BASE_PATH && env.VITE_BASE_PATH.trim().length
      ? env.VITE_BASE_PATH.replace(/\/?$/, '/')
      : './'

  return {
    plugins: [vue(), vueDevTools()],
    base,
    build: {
      outDir: '../backend/src/boardgames_api/static',
      emptyOutDir: true,
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
  }
})
