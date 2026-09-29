import { local, onSystemSchemeChange, systemScheme } from './common'
import type { Haptic, MainButtonState, Platform, ShellColors } from './types'

/* Минимальные типы Telegram WebApp, которые использует форма. */
interface TgButton {
  setParams(p: Record<string, unknown>): void
  showProgress(leaveActive?: boolean): void
  hideProgress(): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
  show(): void
  hide(): void
}
interface TgWebApp {
  initData: string
  colorScheme?: 'light' | 'dark'
  version?: string
  isVersionAtLeast?(v: string): boolean
  onEvent?(event: string, cb: () => void): void
  MainButton?: TgButton
  BackButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
  HapticFeedback?: {
    impactOccurred(style: string): void
    notificationOccurred(type: string): void
    selectionChanged(): void
  }
  CloudStorage?: {
    getItem(key: string, cb: (err: unknown, value?: string) => void): void
    setItem(key: string, value: string, cb?: (err: unknown) => void): void
    removeItem(key: string, cb?: (err: unknown) => void): void
  }
  setHeaderColor?(c: string): void
  setBackgroundColor?(c: string): void
  setBottomBarColor?(c: string): void
  disableVerticalSwipes?(): void
  openLink?(url: string): void
  close?(): void
  ready?(): void
  expand?(): void
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp }
  }
}

export function createTelegram(): Platform {
  const tg = window.Telegram?.WebApp
  const at = (v: string) => !!tg?.isVersionAtLeast?.(v)
  let mainHandler: (() => void) | null = null
  let backHandler: (() => void) | null = null

  const cloud = at('6.9') ? tg?.CloudStorage : undefined

  return {
    name: 'telegram',
    initData: tg?.initData ?? '',
    nativeMainButton: !!tg?.MainButton,
    nativeBackButton: !!tg?.BackButton && at('6.1'),
    colorScheme: () => tg?.colorScheme ?? systemScheme(),
    onColorSchemeChange(cb) {
      if (tg?.onEvent) tg.onEvent('themeChanged', cb)
      else onSystemSchemeChange(cb)
    },
    applyShell(c: ShellColors) {
      try {
        if (at('6.1')) {
          tg?.setHeaderColor?.(c.chrome)
          tg?.setBackgroundColor?.(c.bg)
        }
        if (at('7.10')) tg?.setBottomBarColor?.(c.chrome)
      } catch {
        /* старый клиент — остаются цвета Telegram */
      }
    },
    setMainButton(state: MainButtonState | null, onClick) {
      const mb = tg?.MainButton
      if (!mb) return
      if (mainHandler) mb.offClick(mainHandler)
      mainHandler = null
      if (!state) {
        mb.hideProgress()
        mb.hide()
        return
      }
      const css = getComputedStyle(document.documentElement)
      const v = (n: string) => css.getPropertyValue(n).trim()
      const active = state.enabled && !state.loading
      const fill = state.tone === 'danger' ? v('--c-danger-fill') : v('--c-accent')
      const ink = state.tone === 'danger' ? v('--c-on-danger') : v('--c-on-accent')
      mb.setParams({
        text: state.text,
        color: state.enabled ? fill : v('--c-disabled-bg'),
        text_color: state.enabled ? ink : v('--c-disabled-ink'),
        is_active: active,
        is_visible: true,
      })
      if (state.loading) mb.showProgress(false)
      else mb.hideProgress()
      if (onClick) {
        mainHandler = () => {
          if (state.enabled && !state.loading) onClick()
        }
        mb.onClick(mainHandler)
      }
    },
    setBackButton(visible, onClick) {
      const bb = tg?.BackButton
      if (!bb) return
      if (backHandler) bb.offClick(backHandler)
      backHandler = null
      if (visible && onClick) {
        backHandler = onClick
        bb.onClick(backHandler)
        bb.show()
      } else bb.hide()
    },
    haptic(kind: Haptic) {
      const h = at('6.1') ? tg?.HapticFeedback : undefined
      if (!h) return
      if (kind === 'select') h.selectionChanged()
      else h.notificationOccurred(kind)
    },
    storageGet(key) {
      if (!cloud) return Promise.resolve(local.get(key))
      return new Promise((resolve) => {
        cloud.getItem(key, (err, value) => resolve(!err && value ? value : local.get(key)))
      })
    },
    storageSet(key, value) {
      local.set(key, value)
      if (!cloud) return Promise.resolve()
      return new Promise((resolve) => cloud.setItem(key, value, () => resolve()))
    },
    storageRemove(key) {
      local.remove(key)
      if (!cloud) return Promise.resolve()
      return new Promise((resolve) => cloud.removeItem(key, () => resolve()))
    },
    openLink(url) {
      if (tg?.openLink) tg.openLink(url)
      else window.open(url, '_blank', 'noopener')
    },
    close() {
      tg?.close?.()
    },
    ready() {
      tg?.ready?.()
      tg?.expand?.()
      if (at('7.7')) tg?.disableVerticalSwipes?.()
    },
  }
}
