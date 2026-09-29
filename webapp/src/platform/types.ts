export type ColorScheme = 'light' | 'dark'
export type Haptic = 'select' | 'success' | 'error' | 'warning'

export interface MainButtonState {
  text: string
  enabled: boolean
  loading: boolean
  /** Цвет кнопки: обычная (accent) или опасное действие. */
  tone?: 'accent' | 'danger'
}

/** Цвета темы, которые адаптер передаёт оболочке мессенджера. */
export interface ShellColors {
  bg: string
  chrome: string
  accent: string
  onAccent: string
  disabledBg: string
  disabledInk: string
}

/** Что форма берёт у мессенджера (contracts/platform-adapter.md). */
export interface Platform {
  readonly name: 'telegram' | 'max'
  readonly initData: string
  /** Мессенджер сам рисует главную кнопку и «Назад». */
  readonly nativeMainButton: boolean
  readonly nativeBackButton: boolean
  colorScheme(): ColorScheme
  onColorSchemeChange(cb: () => void): void
  applyShell(colors: ShellColors): void
  setMainButton(state: MainButtonState | null, onClick: (() => void) | null): void
  setBackButton(visible: boolean, onClick: (() => void) | null): void
  haptic(kind: Haptic): void
  storageGet(key: string): Promise<string | null>
  storageSet(key: string, value: string): Promise<void>
  storageRemove(key: string): Promise<void>
  openLink(url: string): void
  close(): void
  ready(): void
}
