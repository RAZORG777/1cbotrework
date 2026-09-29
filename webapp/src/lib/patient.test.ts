import { describe, expect, it } from 'vitest'
import { birthDateError, cleanPatient, formatBirthDate, formatPhone, MESSAGES, phoneDigits, pluralFields, validatePatient } from './patient'

const today = new Date(2026, 8, 29)
const ok = { last_name: 'Смирнова', first_name: 'Ольга', middle_name: '', birth_date: '14.03.1961', phone: '+7 (916) 134-23-31' }

describe('телефон', () => {
  it('маска с любого начала', () => {
    expect(formatPhone('9161342331')).toBe('+7 (916) 134-23-31')
    expect(formatPhone('89161342331')).toBe('+7 (916) 134-23-31')
    expect(formatPhone('+7 (91')).toBe('+7 (91')
    expect(formatPhone('+7 (916')).toBe('+7 (916)')
    expect(formatPhone('')).toBe('')
  })
  it('цифры без кода страны', () => {
    expect(phoneDigits('+7 (916) 134-23-31')).toBe('9161342331')
    expect(phoneDigits('8 916 134 23 31')).toBe('9161342331')
    expect(phoneDigits('+7 (916) 134-23-3')).toBe('916134233')
  })
})

describe('дата рождения', () => {
  it('маска', () => {
    expect(formatBirthDate('14031961')).toBe('14.03.1961')
    expect(formatBirthDate('1403')).toBe('14.03')
    expect(formatBirthDate('1')).toBe('1')
  })
  it('проверка', () => {
    expect(birthDateError('14.03.1961', today)).toBeNull()
    expect(birthDateError('31.02.1990', today)).toBe(MESSAGES.birthInvalid)
    expect(birthDateError('14.03.2961', today)).toBe(MESSAGES.birthFuture)
    expect(birthDateError('01.01.1899', today)).toBe(MESSAGES.birthOld)
    expect(birthDateError('14.3.61', today)).toBe(MESSAGES.birthFormat)
    expect(birthDateError('', today)).toBe(MESSAGES.required)
    expect(birthDateError('29.09.2026', today)).toBeNull()
  })
})

describe('форма пациента', () => {
  it('корректная без ошибок', () => {
    expect(validatePatient(ok, true, today)).toEqual({})
  })
  it('ошибки у полей и согласия', () => {
    const e = validatePatient({ ...ok, first_name: ' ', phone: '+7 (916) 134-23', last_name: 'Smirnova1' }, false, today)
    expect(Object.keys(e).sort()).toEqual(['consent', 'first_name', 'last_name', 'phone'])
    expect(e.phone).toBe(MESSAGES.phone)
  })
  it('двойные фамилии и отчество необязательно', () => {
    expect(validatePatient({ ...ok, last_name: 'Римская-Корсакова', middle_name: '' }, true, today)).toEqual({})
  })
  it('очистка перед отправкой', () => {
    expect(cleanPatient({ ...ok, last_name: ' Смирнова ' })).toMatchObject({ last_name: 'Смирнова', phone: '+79161342331' })
  })
  it('склонение', () => {
    expect([1, 2, 5, 11, 22].map(pluralFields)).toEqual(['1 поле', '2 поля', '5 полей', '11 полей', '22 поля'])
  })
})
