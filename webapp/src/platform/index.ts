import { createMax } from './max'
import { createTelegram } from './telegram'
import type { Platform } from './types'

export type { Platform, Haptic, MainButtonState, ColorScheme, ShellColors } from './types'

let instance: Platform | null = null

/** Адаптер выбирается режимом сборки: ненужная ветка вырезается при сборке. */
export function platform(): Platform {
  if (!instance) instance = __PLATFORM__ === 'max' ? createMax() : createTelegram()
  return instance
}
