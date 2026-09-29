import { describe, expect, it } from 'vitest'
import { buildDays, firstPageWithSlots, groupByPart, nextFreeAfter, pageOf, partOf } from './schedule'

const today = new Date(2026, 8, 29)

describe('части дня', () => {
  it('границы', () => {
    expect(['09:00', '11:59', '12:00', '17:59', '18:00'].map(partOf)).toEqual(['morning', 'morning', 'day', 'day', 'evening'])
  })
  it('группы без пустых', () => {
    expect(groupByPart(['09:30', '14:30']).map((g) => g.label)).toEqual(['Утро', 'День'])
  })
})

describe('дни', () => {
  const sched = { '2026-09-29': ['09:00', '15:00', '15:00'], '2026-10-02': ['14:30', '09:30'], '2026-10-12': ['10:00'] }
  it('горизонт, дубли, сортировка, прошедшее время сегодня', () => {
    const days = buildDays(sched, today, new Date(2026, 8, 29, 12, 0))
    expect(days).toHaveLength(31)
    expect(days[0]).toEqual({ date: '2026-09-29', slots: ['15:00'] })
    expect(days[3]).toEqual({ date: '2026-10-02', slots: ['09:30', '14:30'] })
  })
  it('страницы и ближайший свободный день', () => {
    const days = buildDays({ '2026-10-12': ['10:00'] }, today)
    expect(firstPageWithSlots(days)).toBe(2)
    expect(pageOf(days, 0)).toHaveLength(6)
    expect(nextFreeAfter(days, 0)?.date).toBe('2026-10-12')
    expect(nextFreeAfter(days, 2)).toBeNull()
  })
})
