import { api } from '@/api/client'
import { booking, root } from './booking'

export function onAccessError(kind: 'access' | 'expired'): void {
  booking.accessKind = kind
  root('access')
}

/** Активная запись с сервера бота (FR-010). */
export async function refreshActive(): Promise<boolean> {
  const r = await api.myAppointment()
  booking.active = r.has_appointment && r.data ? r.data : null
  return !!booking.active
}
