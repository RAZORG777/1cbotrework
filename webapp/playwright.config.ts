import { defineConfig, devices } from '@playwright/test'

// Сценарии идут по настоящим сборкам (vite preview). SDK мессенджеров и API ботов — заглушки (research R9).
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: [['list']],
  use: {
    ...devices['Pixel 7'],
    viewport: { width: 390, height: 844 },
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    launchOptions: { executablePath },
  },
  projects: [
    { name: 'telegram', use: { baseURL: 'http://127.0.0.1:4173/' }, metadata: { platform: 'telegram' } },
    { name: 'max', use: { baseURL: 'http://127.0.0.1:4174/max/' }, metadata: { platform: 'max' } },
  ],
  webServer: [
    { command: 'npm run preview:telegram', url: 'http://127.0.0.1:4173/', reuseExistingServer: !process.env.CI },
    { command: 'npm run preview:max', url: 'http://127.0.0.1:4174/max/', reuseExistingServer: !process.env.CI },
  ],
})
