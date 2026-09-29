import { describe, expect, it } from 'vitest'
import { formatPrice, initials, longDate, monthsLabel, shortDate, shortName } from './format'

describe('формат', () => {
  it('даты', () => {
    expect(shortDate('2026-10-02')).toBe('пт, 2 октября')
    expect(longDate('2026-10-02')).toBe('в пятницу, 2 октября')
    expect(longDate('2026-09-29')).toBe('во вторник, 29 сентября')
    expect(monthsLabel(['2026-09-30', '2026-10-05'])).toBe('Сентябрь – октябрь')
    expect(monthsLabel(['2026-10-01'])).toBe('Октябрь')
  })
  it('цены и имена', () => {
    expect(formatPrice(2500).replace(/\s/g, ' ')).toBe('2 500 ₽')
    expect(formatPrice(null)).toBe('')
    expect(shortName('Иванова Анна Сергеевна')).toBe('Иванова А. С.')
    expect(initials('Иванова Анна Сергеевна')).toBe('АИ')
  })
})
