import { api } from '@/api/client'
import type { Doctor, Service } from '@/api/types'
import { mergeBranchServices, type ServiceItem } from '@/lib/services'

/** Кэш справочников на время сессии формы: повторный заход на шаг не ждёт 1С. */
const doctors = new Map<string, Promise<Doctor[]>>()
const services = new Map<string, Promise<Service[]>>()
const branchServices = new Map<string, Promise<ServiceItem[]>>()

function cached<T>(map: Map<string, Promise<T>>, key: string, load: () => Promise<T>): Promise<T> {
  let p = map.get(key)
  if (!p) {
    p = load()
    map.set(key, p)
    p.catch(() => map.delete(key)) // ошибку не кэшируем — «Повторить» идёт в 1С
  }
  return p
}

export const catalog = {
  doctors: (branch: string) => cached(doctors, branch, () => api.doctors(branch)),
  services: (doctorId: string) => cached(services, doctorId, () => api.services(doctorId)),
  branchServices: (branch: string) =>
    cached(branchServices, branch, async () => {
      const docs = await catalog.doctors(branch)
      const perDoctor = await Promise.all(
        docs.map(async (doctor) => ({ doctor, services: await catalog.services(doctor.id).catch(() => [] as Service[]) })),
      )
      return mergeBranchServices(perDoctor)
    }),
}
