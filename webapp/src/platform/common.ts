import type { ColorScheme } from './types'

const media = () =>
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

export function systemScheme(): ColorScheme {
  return media()?.matches ? 'dark' : 'light'
}

export function onSystemSchemeChange(cb: () => void): void {
  media()?.addEventListener?.('change', cb)
}

export const local = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(key, value)
    } catch {
      /* приватный режим или запрет хранилища — форма работает без памяти */
    }
  },
  remove(key: string): void {
    try {
      window.localStorage.removeItem(key)
    } catch {
      /* см. выше */
    }
  },
}
