import { ref } from 'vue'
import { platform } from '@/platform'
import { local } from '@/platform/common'

/** Выбор оформления: как в мессенджере или вручную. Хранится на устройстве. */
export type ThemePref = 'auto' | 'light' | 'dark'

const KEY = 'yasno_theme'
function parse(v: string | null): ThemePref | null {
  return v === 'light' || v === 'dark' || v === 'auto' ? v : null
}

// Сразу из localStorage — чтобы не мигала тема, пока отвечает хранилище мессенджера.
export const themePref = ref<ThemePref>(parse(local.get(KEY)) ?? 'auto')

export function effectiveScheme(): 'light' | 'dark' {
  return themePref.value === 'auto' ? platform().colorScheme() : themePref.value
}

export async function loadThemePref(): Promise<void> {
  const v = parse(await platform().storageGet(KEY))
  if (v) themePref.value = v
}

export function setThemePref(v: ThemePref): void {
  themePref.value = v
  platform().storageSet(KEY, v).catch(() => undefined)
}
