import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'
  const backendPort = process.env.MOVIEPOP_ELECTRON_DEV === '1'
    ? (process.env.MOVIEPOP_BACKEND_PORT || '18987')
    : '8000'
  const backendTarget = process.env.VITE_API_TARGET || `http://127.0.0.1:${backendPort}`
  
  return {
    base: isProduction ? './' : '/',
    build: {
      outDir: 'dist/renderer',
    },
    server: {
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true
        },
        '/covers': {
          target: backendTarget,
          changeOrigin: true
        }
      }
    },
    plugins: [
      vue(),
      vueDevTools(),
      AutoImport({
        imports: ['vue', 'vue-router'],
        dts: true,
      }),
      Components({
        resolvers: [NaiveUiResolver()],
        dts: true,
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
  }
})
