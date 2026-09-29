import { describe, expect, it } from 'vitest'
import { displayName, groupServices, matches, mergeBranchServices, toItem } from './services'

describe('услуги', () => {
  it('псевдонимы и хвостовые точки', () => {
    expect(displayName('Комплексная офтальмологическая диагностика с консультацией врача - офтальмолога..')).toBe('Комплексная диагностика')
    expect(displayName('Подбор очков..')).toBe('Подбор очков')
  })
  it('первичные и повторные', () => {
    const g = groupServices([toItem({ id: '1', name: 'Консультация' }), toItem({ id: '2', name: 'Повторная консультация' })])
    expect(g.primary.map((s) => s.id)).toEqual(['1'])
    expect(g.repeat.map((s) => s.id)).toEqual(['2'])
  })
  it('услуги филиала со списком врачей', () => {
    const a = { id: 'a', full_name: 'Иванова' }
    const b = { id: 'b', full_name: 'Петров' }
    const merged = mergeBranchServices([
      { doctor: a, services: [{ id: 's1', name: 'Консультация' }] },
      { doctor: b, services: [{ id: 's1', name: 'Консультация' }, { id: 's2', name: 'Аблация' }] },
    ])
    expect(merged.map((s) => s.id)).toEqual(['s2', 's1'])
    expect(merged[1].doctors!.map((d) => d.id)).toEqual(['a', 'b'])
  })
  it('поиск без учёта регистра и ё', () => {
    expect(matches('Фёдорова', 'федор')).toBe(true)
  })
})
