import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/client'
import { classify } from './errors'

describe('коды ошибок', () => {
  it('реакция по коду контракта', () => {
    const k = (code: string, status = 200) => classify(new ApiError(code, status))
    expect(k('OPEN_FROM_BOT', 401)).toBe('access')
    expect(k('SESSION_EXPIRED', 401)).toBe('expired')
    expect(k('SLOT_TAKEN')).toBe('slot_taken')
    expect(k('SECOND_BOOKING_ERROR')).toBe('second_booking')
    expect(k('BAD_PHONE', 422)).toBe('field')
    expect(k('BAD_BIRTH_DATE', 422)).toBe('field')
    expect(k('PD_CONSENT_REQUIRED', 422)).toBe('consent')
    expect(k('NOT_FOUND', 404)).toBe('not_found')
    expect(k('SERVICE_UNAVAILABLE', 502)).toBe('general')
    expect(k('ONEC_ERROR')).toBe('general')
    expect(classify(new Error('сеть'))).toBe('general')
  })
})
