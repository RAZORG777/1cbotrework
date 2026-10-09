import { platform } from '@/platform'
import type {
  BookingPayload,
  Doctor,
  MyAppointmentResponse,
  ResultResponse,
  ScheduleResponse,
  Service,
} from './types'

/** Ошибка с кодом из контракта (contracts/webapp-api.md). */
export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    message?: string,
  ) {
    super(message || code)
  }
}

export const TIMEOUT_MS = 20_000
const BASE = import.meta.env.BASE_URL // «/» или «/max/»

function url(path: string): string {
  return BASE + path.replace(/^\//, '')
}

async function request<T>(path: string, init: RequestInit = {}, retry = 0): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(url(path), {
      ...init,
      signal: ctrl.signal,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        Authorization: `tma ${platform().initData}`,
        ...(init.headers || {}),
      },
    })
  } catch {
    clearTimeout(timer)
    // Сбой сети: справочники повторяем один раз, запись — никогда (FR-023).
    if (retry > 0) return request<T>(path, init, retry - 1)
    throw new ApiError('NETWORK', 0)
  }
  clearTimeout(timer)
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>
  if (res.status === 401) throw new ApiError(String(body.error || 'OPEN_FROM_BOT'), 401)
  if (!res.ok) {
    throw new ApiError(String(body.error || 'SERVICE_UNAVAILABLE'), res.status, body.message as string)
  }
  return body as T
}

function list<T extends { id?: unknown }>(data: unknown): T[] {
  const arr = Array.isArray(data)
    ? data
    : data && typeof data === 'object' && Array.isArray((data as { data?: unknown }).data)
      ? (data as { data: unknown[] }).data
      : []
  // Служебные элементы 1С: {"id":"empty"} — пусто, {"id":"error"} — ошибка.
  if (arr.some((x) => (x as { id?: unknown })?.id === 'error')) throw new ApiError('ONEC_ERROR', 200)
  return (arr as T[]).filter((x) => x && x.id !== 'empty')
}

/** Отказ в ответе 200 со status=error превращается в ApiError. */
function result(r: ResultResponse): ResultResponse {
  if (r.status !== 'success') throw new ApiError(r.error || 'ONEC_ERROR', 200, r.message)
  return r
}

const q = encodeURIComponent

export const api = {
  config: () => request<{ pd_policy_url?: string }>('config', {}, 1),
  doctors: async (branch: string) => list<Doctor>(await request(`doctors?branch=${q(branch)}`, {}, 1)),
  services: async (doctorId: string) => list<Service>(await request(`services?doctor_id=${q(doctorId)}`, {}, 1)),
  schedule: (doctorId: string, branch: string, start: string, end: string) =>
    request<ScheduleResponse>(
      `schedule?doctor_id=${q(doctorId)}&start_date=${start}&end_date=${end}&branch=${q(branch)}`,
      {},
      1,
    ),
  myAppointment: () => request<MyAppointmentResponse>('my_appointment', {}, 1),
  book: async (p: BookingPayload) =>
    result(await request<ResultResponse>('book', { method: 'POST', body: JSON.stringify(p) })),
  reschedule: async (p: BookingPayload) =>
    result(await request<ResultResponse>('reschedule', { method: 'POST', body: JSON.stringify(p) })),
  cancel: async () => result(await request<ResultResponse>('cancel', { method: 'POST', body: '{}' })),
  /** Шаг воронки (specs/008-daily-report-funnel): без ожидания и без ошибок для пациента. */
  track: (step: FunnelStep) => {
    request('track', { method: 'POST', body: JSON.stringify({ step }) }).catch(() => undefined)
  },
}

export type FunnelStep = 'open' | 'branch' | 'doctor' | 'time'
