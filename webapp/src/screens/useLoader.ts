import { shallowRef, type Ref } from 'vue'
import { ApiError } from '@/api/client'
import { classify } from '@/lib/errors'
import { onAccessError } from '@/state/session'

export interface Loader<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  error: Ref<boolean>
  load: () => Promise<void>
}

/** Загрузка с флагами для скелетона и «Повторить»; 401 уводит на экран доступа. */
export function useLoader<T>(fn: () => Promise<T>): Loader<T> {
  const data = shallowRef<T | null>(null) as Ref<T | null>
  const loading = shallowRef(false)
  const error = shallowRef(false)
  let seq = 0
  async function load() {
    const my = ++seq
    loading.value = data.value === null
    error.value = false
    try {
      const v = await fn()
      if (my === seq) data.value = v
    } catch (e) {
      if (my !== seq) return
      const kind = classify(e)
      if (e instanceof ApiError && (kind === 'access' || kind === 'expired')) onAccessError(kind)
      else error.value = true
    } finally {
      if (my === seq) loading.value = false
    }
  }
  return { data, loading, error, load }
}
