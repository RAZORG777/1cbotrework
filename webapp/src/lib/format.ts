/** Даты и цены по-русски. Все даты расписания — строки YYYY-MM-DD в часовом поясе клиники. */

const MONTHS_GEN = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
const MONTHS_NOM = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
const WD_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
const WD_ACC = ['воскресенье', 'понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу']

export function parseISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toISO(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function addDays(d: Date, n: number): Date {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

export const weekdayShort = (iso: string) => WD_SHORT[parseISO(iso).getDay()]
export const dayNum = (iso: string) => parseISO(iso).getDate()

/** «пт, 2 октября» */
export function shortDate(iso: string): string {
  const d = parseISO(iso)
  return `${WD_SHORT[d.getDay()]}, ${d.getDate()} ${MONTHS_GEN[d.getMonth()]}`
}

/** «в пятницу, 2 октября» */
export function longDate(iso: string): string {
  const d = parseISO(iso)
  const prep = d.getDay() === 2 ? 'во' : 'в'
  return `${prep} ${WD_ACC[d.getDay()]}, ${d.getDate()} ${MONTHS_GEN[d.getMonth()]}`
}

/** Подпись страницы дат: «Октябрь» или «Сентябрь – октябрь». */
export function monthsLabel(isos: string[]): string {
  if (!isos.length) return ''
  const first = parseISO(isos[0]).getMonth()
  const last = parseISO(isos[isos.length - 1]).getMonth()
  const cap = (s: string) => s[0].toUpperCase() + s.slice(1)
  return first === last ? cap(MONTHS_NOM[first]) : `${cap(MONTHS_NOM[first])} – ${MONTHS_NOM[last]}`
}

export function formatPrice(price: unknown): string {
  const n = typeof price === 'string' ? Number(price.replace(/\s/g, '').replace(',', '.')) : Number(price)
  if (!price || !Number.isFinite(n) || n <= 0) return ''
  return `${new Intl.NumberFormat('ru-RU').format(Math.round(n))} ₽`
}

/** «Иванова Анна Сергеевна» → «Иванова А. С.» */
export function shortName(full: string): string {
  const [last, ...rest] = full.trim().split(/\s+/)
  if (!rest.length) return last || ''
  return `${last} ${rest.map((p) => p[0] + '.').join(' ')}`
}

export function initials(full: string): string {
  const parts = full.trim().split(/\s+/)
  return ((parts[1]?.[0] || '') + (parts[0]?.[0] || '')).toUpperCase() || '?'
}
