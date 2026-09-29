import { ApiError } from '@/api/client'

export const CLINIC_PHONE = '8 (800) 301-01-67'
export const CLINIC_PHONE_HREF = 'tel:88003010167'

export type ErrorKind =
  | 'access'
  | 'expired'
  | 'slot_taken'
  | 'second_booking'
  | 'field'
  | 'consent'
  | 'not_found'
  | 'general'

/** Реакция формы на код ответа (contracts/webapp-api.md › Коды ошибок). */
export function classify(e: unknown): ErrorKind {
  const code = e instanceof ApiError ? e.code : ''
  switch (code) {
    case 'OPEN_FROM_BOT':
      return 'access'
    case 'SESSION_EXPIRED':
      return 'expired'
    case 'SLOT_TAKEN':
      return 'slot_taken'
    case 'SECOND_BOOKING_ERROR':
      return 'second_booking'
    case 'BAD_PHONE':
    case 'BAD_BIRTH_DATE':
      return 'field'
    case 'PD_CONSENT_REQUIRED':
      return 'consent'
    case 'NOT_FOUND':
      return 'not_found'
    default:
      return 'general'
  }
}

export const GENERAL_MESSAGE = 'Сервис записи временно недоступен. Попробуйте ещё раз или позвоните в клинику.'
