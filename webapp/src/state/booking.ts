import { reactive } from 'vue'
import type { ActiveAppointment, Doctor } from '@/api/types'
import type { FieldErrors, PatientFields } from '@/lib/patient'
import type { ServiceItem } from '@/lib/services'

export type Screen =
  | 'loading'
  | 'access'
  | 'home'
  | 'choose'
  | 'doctorServices'
  | 'serviceDoctors'
  | 'time'
  | 'patient'
  | 'success'
  | 'my'

export interface BookedResult {
  date: string
  time: string
  doctorName: string
  serviceName: string
  branch: string
  patientName: string
  rescheduled: boolean
}

export const emptyPatient = (): PatientFields => ({ last_name: '', first_name: '', middle_name: '', birth_date: '', phone: '' })

/** Состояние пути записи и стек экранов (data-model › BookingDraft, research R4). */
export const booking = reactive({
  stack: ['loading'] as Screen[],
  dir: 'fwd' as 'fwd' | 'back',
  accessKind: 'access' as 'access' | 'expired',
  pdPolicyUrl: '',

  branch: '' as string,
  path: 'doctor' as 'doctor' | 'service',
  doctor: null as Doctor | null,
  service: null as ServiceItem | null,
  date: '' as string,
  time: '' as string,
  mode: 'book' as 'book' | 'reschedule',

  active: null as ActiveAppointment | null,
  takenSlots: [] as string[],
  slotTakenNotice: '' as string,

  profileKey: 'me' as string,
  patient: emptyPatient(),
  remember: true,
  notify: true,
  consent: false,
  errors: {} as FieldErrors,

  result: null as BookedResult | null,
})

export const top = (): Screen => booking.stack[booking.stack.length - 1]

export function go(screen: Screen): void {
  booking.dir = 'fwd'
  booking.stack.push(screen)
}

export function back(): void {
  if (booking.stack.length <= 1) return
  booking.dir = 'back'
  booking.stack.pop()
}

/** Вернуться к экрану, если он есть в стеке (например, «время заняли» → «Дата и время»). */
export function backTo(screen: Screen): void {
  const idx = booking.stack.lastIndexOf(screen)
  if (idx < 0) return
  booking.dir = 'back'
  booking.stack.splice(idx + 1)
}

/** Новый корень: «Моя запись», «Филиал», экран доступа. */
export function root(screen: Screen, dir: 'fwd' | 'back' = 'fwd'): void {
  booking.dir = dir
  booking.stack = [screen]
}

export function resetDraft(): void {
  booking.branch = ''
  booking.path = 'doctor'
  booking.doctor = null
  booking.service = null
  booking.date = ''
  booking.time = ''
  booking.mode = 'book'
  booking.takenSlots = []
  booking.slotTakenNotice = ''
  booking.consent = false
  booking.errors = {}
}

export const slotKey = (date: string, time: string) => `${date} ${time}`
