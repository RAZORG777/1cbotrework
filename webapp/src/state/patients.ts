import { reactive } from 'vue'
import { platform } from '@/platform'
import type { PatientFields } from '@/lib/patient'

/** Сохранённые пациенты — только на устройстве пользователя (FR-019, data-model › SavedPatient). */
export interface SavedPatient extends PatientFields {
  key: string
  label: string
}

const KEY = 'yasno_patients_v2'
const OLD_ME = 'yasno_patient_data'
const OLD_FAMILY = 'yasno_family_profiles'

export const patients = reactive<{ list: SavedPatient[]; loaded: boolean }>({ list: [], loaded: false })

function pick(o: Record<string, unknown>): PatientFields | null {
  const s = (k: string) => (typeof o[k] === 'string' ? (o[k] as string) : '')
  const p = { last_name: s('last_name'), first_name: s('first_name'), middle_name: s('middle_name'), birth_date: s('birth_date'), phone: s('phone') }
  return p.first_name || p.last_name ? p : null
}

function parse(raw: string | null): unknown {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export async function loadPatients(): Promise<void> {
  const p = platform()
  const stored = parse(await p.storageGet(KEY))
  if (Array.isArray(stored)) {
    patients.list = stored.filter((x) => x && typeof x === 'object' && typeof x.key === 'string') as SavedPatient[]
  } else {
    // Перенос профилей старой формы.
    const list: SavedPatient[] = []
    const me = parse(await p.storageGet(OLD_ME))
    const mePick = me && typeof me === 'object' ? pick(me as Record<string, unknown>) : null
    if (mePick) list.push({ ...mePick, key: 'me', label: 'Я' })
    const family = parse(await p.storageGet(OLD_FAMILY))
    if (Array.isArray(family)) {
      family.forEach((f, i) => {
        const fp = f && typeof f === 'object' ? pick(f as Record<string, unknown>) : null
        if (fp) list.push({ ...fp, key: `f${Date.now()}${i}`, label: fp.first_name || 'Родственник' })
      })
    }
    patients.list = list
    if (list.length) {
      await p.storageSet(KEY, JSON.stringify(list))
      await p.storageRemove(OLD_ME)
      await p.storageRemove(OLD_FAMILY)
    }
  }
  patients.loaded = true
}

/** Сохранить «Я» (key = 'me') или родственника (новый key). Возвращает key. */
export async function savePatient(key: string | null, fields: PatientFields): Promise<string> {
  const k = key ?? `f${Date.now()}`
  const label = k === 'me' ? 'Я' : fields.first_name || 'Родственник'
  const item: SavedPatient = { ...fields, key: k, label }
  const idx = patients.list.findIndex((x) => x.key === k)
  if (idx >= 0) patients.list.splice(idx, 1, item)
  else if (k === 'me') patients.list.unshift(item)
  else patients.list.push(item)
  await platform().storageSet(KEY, JSON.stringify(patients.list))
  return k
}

export function patientByKey(key: string): SavedPatient | undefined {
  return patients.list.find((x) => x.key === key)
}
