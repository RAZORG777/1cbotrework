/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Одна форма — две сборки (research R1): режим задаёт базу адреса, каталог бота и SDK.
const TARGETS = {
  telegram: {
    base: '/',
    outDir: '../telegram_bot/static/app',
    sdk: 'https://telegram.org/js/telegram-web-app.js',
  },
  max: {
    base: '/max/',
    outDir: '../max_bot/static/app',
    sdk: 'https://st.max.ru/js/max-web-app.js',
  },
} as const

type Target = keyof typeof TARGETS

function messengerSdk(src: string): Plugin {
  return {
    name: 'messenger-sdk',
    transformIndexHtml: () => [{ tag: 'script', attrs: { src }, injectTo: 'head-prepend' }],
  }
}

export default defineConfig(({ mode }) => {
  const target: Target = mode === 'max' ? 'max' : 'telegram'
  const cfg = TARGETS[target]
  return {
    base: cfg.base,
    plugins: [vue(), tailwindcss(), messengerSdk(cfg.sdk)],
    define: { __PLATFORM__: JSON.stringify(target) },
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    build: {
      outDir: cfg.outDir,
      emptyOutDir: true,
      target: 'es2020',
      assetsInlineLimit: 0,
    },
    preview: { port: target === 'max' ? 4174 : 4173, strictPort: true },
    test: {
      environment: 'node',
      include: ['src/**/*.test.ts'],
    },
  }
})
