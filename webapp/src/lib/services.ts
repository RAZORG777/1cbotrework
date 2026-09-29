import type { Doctor, Service } from '@/api/types'

/** Короткие названия длинных услуг 1С (перенесены из старой формы). */
const ALIASES: Record<string, string> = {
  'Комплексная офтальмологическая диагностика с консультацией врача офтальмолога - к.м.н..':
    'Комплексная диагностика (к.м.н.)',
  'Комплексная офтальмологическая диагностика с консультацией врача - офтальмолога при глаукоме':
    'Комплексная диагностика (при глаукоме)',
  'Комплексная офтальмологическая диагностика с консультацией врача - офтальмолога..':
    'Комплексная диагностика',
}

export interface ServiceItem extends Service {
  displayName: string
  repeat: boolean
  doctors?: Doctor[]
}

export function displayName(name: string): string {
  return ALIASES[name] ?? name.replace(/\.{2,}$/, '').trim()
}

export function toItem(s: Service): ServiceItem {
  const dn = displayName(s.name)
  return { ...s, displayName: dn, repeat: /повторн/i.test(dn) }
}

export function groupServices(items: ServiceItem[]): { primary: ServiceItem[]; repeat: ServiceItem[] } {
  return { primary: items.filter((s) => !s.repeat), repeat: items.filter((s) => s.repeat) }
}

/** Услуги филиала: объединение услуг всех врачей, у каждой — список врачей, кто её оказывает. */
export function mergeBranchServices(perDoctor: { doctor: Doctor; services: Service[] }[]): ServiceItem[] {
  const map = new Map<string, ServiceItem>()
  for (const { doctor, services } of perDoctor) {
    for (const s of services) {
      const item = map.get(s.id) ?? { ...toItem(s), doctors: [] }
      if (!item.doctors!.some((d) => d.id === doctor.id)) item.doctors!.push(doctor)
      map.set(s.id, item)
    }
  }
  return [...map.values()].sort((a, b) => a.displayName.localeCompare(b.displayName, 'ru'))
}

export function matches(text: string, query: string): boolean {
  const norm = (s: string) => s.toLowerCase().replace(/ё/g, 'е')
  return norm(text).includes(norm(query.trim()))
}
