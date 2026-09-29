import { addDays, parseISO, toISO } from './format'

/** Расписание врача (data-model.md › ScheduleDay). */
export interface ScheduleDay {
  date: string
  slots: string[]
}

export type DayPart = 'morning' | 'day' | 'evening'
export const DAY_PART_LABEL: Record<DayPart, string> = { morning: 'Утро', day: 'День', evening: 'Вечер' }

export const HORIZON_DAYS = 30
export const PAGE_SIZE = 6

export function partOf(time: string): DayPart {
  const h = Number(time.slice(0, 2))
  if (h < 12) return 'morning'
  if (h < 18) return 'day'
  return 'evening'
}

export function groupByPart(slots: string[]): { part: DayPart; label: string; slots: string[] }[] {
  const parts: DayPart[] = ['morning', 'day', 'evening']
  return parts
    .map((part) => ({ part, label: DAY_PART_LABEL[part], slots: slots.filter((s) => partOf(s) === part) }))
    .filter((g) => g.slots.length > 0)
}

/**
 * Календарь на горизонт: каждый день от сегодня, слоты без дублей по порядку.
 * Прошедшее время сегодняшнего дня отбрасывается.
 */
export function buildDays(
  schedule: Record<string, string[]> | undefined,
  today: Date,
  now: Date = today,
  horizon = HORIZON_DAYS,
): ScheduleDay[] {
  const todayIso = toISO(today)
  const nowHm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  const days: ScheduleDay[] = []
  for (let i = 0; i <= horizon; i++) {
    const iso = toISO(addDays(today, i))
    const raw = schedule?.[iso] ?? []
    let slots = [...new Set(raw.map((s) => s.slice(0, 5)))].sort()
    if (iso === todayIso) slots = slots.filter((s) => s > nowHm)
    days.push({ date: iso, slots })
  }
  return days
}

/** Первая страница, где есть свободный день; иначе 0. */
export function firstPageWithSlots(days: ScheduleDay[], pageSize = PAGE_SIZE): number {
  const idx = days.findIndex((d) => d.slots.length > 0)
  return idx < 0 ? 0 : Math.floor(idx / pageSize)
}

export function pageOf(days: ScheduleDay[], page: number, pageSize = PAGE_SIZE): ScheduleDay[] {
  return days.slice(page * pageSize, page * pageSize + pageSize)
}

export function pageCount(days: ScheduleDay[], pageSize = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(days.length / pageSize))
}

/** Ближайший свободный день после страницы (для «На этой неделе мест нет»). */
export function nextFreeAfter(days: ScheduleDay[], page: number, pageSize = PAGE_SIZE): ScheduleDay | null {
  return days.slice((page + 1) * pageSize).find((d) => d.slots.length > 0) ?? null
}

export function hasAnySlots(days: ScheduleDay[]): boolean {
  return days.some((d) => d.slots.length > 0)
}

export const startEnd = (today: Date, horizon = HORIZON_DAYS) => ({
  start: toISO(today),
  end: toISO(addDays(parseISO(toISO(today)), horizon)),
})
