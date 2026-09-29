import { onBeforeUnmount, shallowRef, watchEffect, type Ref } from 'vue'
import type { MainButtonState } from '@/platform'

export interface MainButtonBinding {
  state: MainButtonState
  onClick: () => void
}

/** Главная кнопка текущего экрана: нативная в Telegram, своя внизу страницы в MAX. */
export const mainButton = shallowRef<MainButtonBinding | null>(null)

export function useMainButton(state: Ref<MainButtonState | null>, onClick: () => void): void {
  const stop = watchEffect(() => {
    const s = state.value
    mainButton.value = s ? { state: { ...s }, onClick } : null
  })
  onBeforeUnmount(() => {
    stop()
    if (mainButton.value?.onClick === onClick) mainButton.value = null
  })
}
