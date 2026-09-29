/** Маски и проверка данных пациента (data-model.md › PatientForm, FR-007). */

export interface PatientFields {
  last_name: string
  first_name: string
  middle_name: string
  birth_date: string
  phone: string
}

export type FieldErrors = Partial<Record<keyof PatientFields | 'consent', string>>

export const MESSAGES = {
  required: 'Заполните поле',
  name: 'Только буквы, пробел и дефис',
  birthFormat: 'Формат: ДД.ММ.ГГГГ',
  birthInvalid: 'Такой даты нет',
  birthFuture: 'Дата в будущем. Формат: ДД.ММ.ГГГГ',
  birthOld: 'Проверьте год рождения',
  phone: 'Нужно 10 цифр после +7',
  consent: 'Без согласия запись невозможна',
} as const

const NAME = /^[A-Za-zА-Яа-яЁё]+(?:[ '\-][A-Za-zА-Яа-яЁё]+)*$/

/** Цифры номера без кода страны: «8 916…», «+7 916…», «916…» → «916…». */
export function phoneDigits(value: string): string {
  let d = value.replace(/\D/g, '')
  const prefixed = value.trim().startsWith('+7') || (d.length === 11 && (d[0] === '7' || d[0] === '8'))
  if (prefixed) d = d.slice(1)
  return d.slice(0, 10)
}

/** Маска ввода телефона: «+7 (916) 134-23-31». */
export function formatPhone(value: string): string {
  const raw = value.replace(/\D/g, '')
  if (!raw) return ''
  let d = raw
  if (d.startsWith('7') || d.startsWith('8')) d = d.slice(1)
  d = d.slice(0, 10)
  let out = '+7'
  if (d.length > 0) out += ' (' + d.slice(0, 3)
  if (d.length >= 3) out += ')'
  if (d.length > 3) out += ' ' + d.slice(3, 6)
  if (d.length > 6) out += '-' + d.slice(6, 8)
  if (d.length > 8) out += '-' + d.slice(8, 10)
  return out
}

/** Маска ввода даты: «14031961» → «14.03.1961». */
export function formatBirthDate(value: string): string {
  const d = value.replace(/\D/g, '').slice(0, 8)
  if (d.length <= 2) return d
  if (d.length <= 4) return `${d.slice(0, 2)}.${d.slice(2)}`
  return `${d.slice(0, 2)}.${d.slice(2, 4)}.${d.slice(4)}`
}

export function birthDateError(value: string, today = new Date()): string | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value.trim())
  if (!m) return value.trim() ? MESSAGES.birthFormat : MESSAGES.required
  const [day, month, year] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return MESSAGES.birthInvalid
  }
  if (year < 1900) return MESSAGES.birthOld
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  if (date > end) return MESSAGES.birthFuture
  return null
}

function nameError(value: string, required: boolean): string | null {
  const v = value.trim()
  if (!v) return required ? MESSAGES.required : null
  if (v.length > 100 || !NAME.test(v)) return MESSAGES.name
  return null
}

export function validatePatient(p: PatientFields, consent: boolean, today = new Date()): FieldErrors {
  const errors: FieldErrors = {}
  const put = (k: keyof FieldErrors, msg: string | null) => {
    if (msg) errors[k] = msg
  }
  put('last_name', nameError(p.last_name, true))
  put('first_name', nameError(p.first_name, true))
  put('middle_name', nameError(p.middle_name, false))
  put('birth_date', birthDateError(p.birth_date, today))
  put('phone', phoneDigits(p.phone).length === 10 ? null : p.phone.trim() ? MESSAGES.phone : MESSAGES.required)
  if (!consent) errors.consent = MESSAGES.consent
  return errors
}

/** Чистое значение для отправки: пробелы убраны, телефон как ввёл пациент (нормализует бот). */
export function cleanPatient(p: PatientFields): PatientFields {
  return {
    last_name: p.last_name.trim(),
    first_name: p.first_name.trim(),
    middle_name: p.middle_name.trim(),
    birth_date: p.birth_date.trim(),
    phone: `+7${phoneDigits(p.phone)}`,
  }
}

export function pluralFields(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return `${n} поле`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} поля`
  return `${n} полей`
}
