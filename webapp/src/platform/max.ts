import { local, onSystemSchemeChange, systemScheme } from './common'
import type { Haptic, Platform } from './types'

/* MAX bridge (dev.max.ru/docs/webapps/bridge): главной кнопки и темы нет, остальное — по наличию. */
interface MaxWebApp {
  initData: string
  BackButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
  HapticFeedback?: {
    impactOccurred(style: string, disableVibrationFallback?: boolean): void
    notificationOccurred(type: string, disableVibrationFallback?: boolean): void
    selectionChanged(disableVibrationFallback?: boolean): void
  }
  DeviceStorage?: {
    getItem(key: string): Promise<unknown> | unknown
    setItem(key: string, value: string): Promise<unknown> | unknown
    removeItem(key: string): Promise<unknown> | unknown
  }
  openLink?(url: string): void
  close?(): void
  ready?(): void
}

declare global {
  interface Window {
    WebApp?: MaxWebApp
  }
}

function pickValue(result: unknown): string | null {
  if (typeof result === 'string') return result
  if (result && typeof result === 'object' && 'value' in result) {
    const v = (result as { value: unknown }).value
    return typeof v === 'string' ? v : null
  }
  return null
}

export function createMax(): Platform {
  const app = window.WebApp
  let backHandler: (() => void) | null = null
  const device = app?.DeviceStorage

  return {
    name: 'max',
    initData: app?.initData ?? '',
    nativeMainButton: false,
    nativeBackButton: !!app?.BackButton,
    colorScheme: systemScheme,
    onColorSchemeChange: onSystemSchemeChange,
    applyShell() {
      /* MAX не даёт управлять цветами оболочки */
    },
    setMainButton() {
      /* своя кнопка внизу страницы (MainAction) */
    },
    setBackButton(visible, onClick) {
      const bb = app?.BackButton
      if (!bb) return
      try {
        if (backHandler) bb.offClick(backHandler)
        backHandler = null
        if (visible && onClick) {
          backHandler = onClick
          bb.onClick(backHandler)
          bb.show()
        } else bb.hide()
      } catch {
        /* сбой SDK MAX: кнопку «Назад» просто не показываем */
      }
    },
    haptic(kind: Haptic) {
      const h = app?.HapticFeedback
      if (!h) return
      try {
        if (kind === 'select') h.selectionChanged(true)
        else h.notificationOccurred(kind, true)
      } catch {
        /* вибрация необязательна */
      }
    },
    async storageGet(key) {
      if (device) {
        try {
          const v = pickValue(await device.getItem(key))
          if (v) return v
        } catch {
          /* десктоп и веб — только localStorage */
        }
      }
      return local.get(key)
    },
    async storageSet(key, value) {
      local.set(key, value)
      try {
        await device?.setItem(key, value)
      } catch {
        /* см. выше */
      }
    },
    async storageRemove(key) {
      local.remove(key)
      try {
        await device?.removeItem(key)
      } catch {
        /* см. выше */
      }
    },
    openLink(url) {
      if (app?.openLink) app.openLink(url)
      else window.open(url, '_blank', 'noopener')
    },
    close() {
      app?.close?.()
    },
    ready() {
      app?.ready?.()
    },
  }
}
