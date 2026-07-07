import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'
  
  return {
    base: isProduction ? './' : '/',
    build: {
      outDir: 'dist/renderer',
    },
    server: {
      proxy: {
        '/api': {
          target: process.env.VITE_API_TARGET || 'http://localhost:8000',
          changeOrigin: true
        },
        '/covers': {
          target: process.env.VITE_API_TARGET || 'http://localhost:8000',
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