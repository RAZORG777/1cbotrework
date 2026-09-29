import type { Branch } from '@/api/types'

/** Филиалы с сайта клиники (yasno-vizhu.com/contacts). Значение `id` уходит в 1С как есть. */
export interface BranchInfo {
  id: Branch
  name: string
  address: string
  phone: string
  phoneHref: string
}

export const BRANCHES: BranchInfo[] = [
  {
    id: 'Профсоюзная',
    name: 'Профсоюзная',
    address: 'ул. Профсоюзная, 76',
    phone: '+7 (495) 101-20-25',
    phoneHref: 'tel:+74951012025',
  },
  {
    id: 'Ватутинки',
    name: 'Новые Ватутинки',
    address: 'ул. 3-я Нововатутинская, 13, корп. 2',
    phone: '+7 (495) 101-01-77',
    phoneHref: 'tel:+74951010177',
  },
]

export function branchInfo(id: string): BranchInfo {
  return BRANCHES.find((b) => b.id === id || b.name === id) ?? BRANCHES[0]
}
