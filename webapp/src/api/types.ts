export type Branch = 'Профсоюзная' | 'Ватутинки'

export interface Doctor {
  id: string
  full_name: string
  specialty_name?: string
  photo_url?: string
  experience?: string
  description?: string
}

export interface Service {
  id: string
  name: string
  price?: number | string | null
}

export interface ScheduleResponse {
  status: string
  schedule?: Record<string, string[]>
}

export interface ActiveAppointment {
  appointment_id: string
  branch: string
  date: string
  time: string
  doctor_id?: string
  doctor_name: string
  service_id?: string
  service_name: string
  confirmed?: boolean
}

export interface MyAppointmentResponse {
  status: string
  has_appointment: boolean
  data?: ActiveAppointment
}

export interface PatientPayload {
  first_name: string
  last_name: string
  middle_name: string
  phone: string
  birth_date: string
}

export interface BookingPayload {
  branch: string
  doctor_id: string
  doctor_name: string
  service_id: string
  service_name: string
  date: string
  time: string
  patient?: PatientPayload
  send_notifications: boolean
  pd_consent: boolean
  old_appointment_id?: string
}

export interface ResultResponse {
  status: 'success' | 'error'
  appointment_id?: string
  error?: string
  message?: string
}
