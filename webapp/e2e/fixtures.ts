import { test as base, expect, type Page, type Route } from '@playwright/test'

/* ---------- Фейковый бот: состояние и ответы API (contracts/webapp-api.md) ---------- */

export interface Active {
  appointment_id: string
  branch: string
  date: string
  time: string
  doctor_id: string
  doctor_name: string
  service_id: string
  service_name: string
  confirmed: boolean
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
export const dayFromToday = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return iso(d)
}

export const DOCTORS = [
  { id: 'doc-1', full_name: 'Иванова Анна Сергеевна', specialty_name: 'Врач-офтальмолог', experience: '15 лет' },
  { id: 'doc-2', full_name: 'Петров Михаил Олегович', specialty_name: 'Офтальмохирург' },
]
export const SERVICES: Record<string, { id: string; name: string; price: number }[]> = {
  'doc-1': [
    { id: 'srv-1', name: 'Консультация офтальмолога', price: 3000 },
    { id: 'srv-2', name: 'Повторная консультация', price: 2000 },
  ],
  'doc-2': [{ id: 'srv-1', name: 'Консультация офтальмолога', price: 3000 }],
}

export class FakeBot {
  active: Active | null = null
  requests: { path: string; body: unknown }[] = []
  /** Код отказа на следующую запись/перенос. */
  nextBookError: { status: number; body: Record<string, unknown> } | null = null
  auth: 'ok' | 'OPEN_FROM_BOT' | 'SESSION_EXPIRED' = 'ok'
  schedule: Record<string, string[]> = {
    [dayFromToday(1)]: ['09:30', '11:00', '14:30', '15:00', '18:30'],
    [dayFromToday(3)]: ['10:00', '12:30'],
  }

  async handle(route: Route): Promise<void> {
    const url = new URL(route.request().url())
    const path = url.pathname.replace(/^\/max/, '').replace(/^\//, '')
    const body = route.request().postData() ? JSON.parse(route.request().postData()!) : null
    this.requests.push({ path, body })
    const json = (status: number, data: unknown) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    if (path === 'config') return json(200, { pd_policy_url: 'https://policy.test/pd.pdf' })
    if (this.auth !== 'ok') return json(401, { error: this.auth })
    switch (path) {
      case 'my_appointment':
        return json(200, this.active ? { status: 'success', has_appointment: true, data: this.active } : { status: 'success', has_appointment: false })
      case 'doctors':
        return json(200, DOCTORS)
      case 'services':
        return json(200, SERVICES[url.searchParams.get('doctor_id') || ''] ?? [{ id: 'empty', name: '' }])
      case 'schedule':
        return json(200, { status: 'success', schedule: this.schedule })
      case 'book':
      case 'reschedule': {
        if (this.nextBookError) {
          const e = this.nextBookError
          this.nextBookError = null
          return json(e.status, e.body)
        }
        const b = body as Record<string, string>
        const id = path === 'book' ? 'appt-1' : 'appt-2'
        this.active = {
          appointment_id: id,
          branch: b.branch,
          date: b.date,
          time: b.time,
          doctor_id: b.doctor_id,
          doctor_name: b.doctor_name,
          service_id: b.service_id,
          service_name: b.service_name,
          confirmed: false,
        }
        return json(200, { status: 'success', appointment_id: id })
      }
      case 'track':
        return json(200, { status: 'ok' })
      case 'cancel':
        if (!this.active) return json(404, { status: 'error', error: 'NOT_FOUND' })
        this.active = null
        return json(200, { status: 'success' })
    }
    return route.fulfill({ status: 404, body: 'nope' })
  }
}

/* ---------- Заглушки SDK мессенджеров ---------- */

function sdkStub({ platform, scheme }: { platform: string; scheme: 'light' | 'dark' }) {
  const w = window as unknown as Record<string, unknown>
  const log: unknown[] = []
  const back = {
    visible: false,
    handlers: [] as (() => void)[],
    show() { this.visible = true },
    hide() { this.visible = false },
    onClick(cb: () => void) { this.handlers.push(cb) },
    offClick(cb: () => void) { this.handlers = this.handlers.filter((h) => h !== cb) },
    click() { this.handlers.forEach((h) => h()) },
  }
  const haptic = {
    impactOccurred: (s: string) => log.push(['impact', s]),
    notificationOccurred: (s: string) => log.push(['notify', s]),
    selectionChanged: () => log.push(['select']),
  }
  w.__haptics = log
  w.__back = back
  if (platform === 'telegram') {
    const main = {
      params: {} as Record<string, unknown>,
      progress: false,
      handlers: [] as (() => void)[],
      setParams(p: Record<string, unknown>) { Object.assign(this.params, p) },
      showProgress() { this.progress = true },
      hideProgress() { this.progress = false },
      onClick(cb: () => void) { this.handlers.push(cb) },
      offClick(cb: () => void) { this.handlers = this.handlers.filter((h) => h !== cb) },
      show() { this.params.is_visible = true },
      hide() { this.params.is_visible = false },
      click() { if (this.params.is_visible) this.handlers.forEach((h) => h()) },
    }
    const events: Record<string, (() => void)[]> = {}
    const tg = {
      initData: 'query_id=stub&user=%7B%22id%22%3A1%7D&auth_date=1&hash=stub',
      version: '8.0',
      colorScheme: scheme,
      isVersionAtLeast: () => true,
      onEvent: (e: string, cb: () => void) => (events[e] = [...(events[e] || []), cb]),
      MainButton: main,
      BackButton: back,
      HapticFeedback: haptic,
      CloudStorage: {
        store: {} as Record<string, string>,
        getItem(k: string, cb: (e: unknown, v?: string) => void) { cb(null, this.store[k] ?? '') },
        setItem(k: string, v: string, cb?: () => void) { this.store[k] = v; cb?.() },
        removeItem(k: string, cb?: () => void) { delete this.store[k]; cb?.() },
      },
      setHeaderColor: () => undefined,
      setBackgroundColor: () => undefined,
      setBottomBarColor: () => undefined,
      disableVerticalSwipes: () => undefined,
      ready: () => undefined,
      expand: () => undefined,
      close: () => { w.__closed = true },
      openLink: () => undefined,
    }
    w.Telegram = { WebApp: tg }
    w.__main = main
    w.__setScheme = (s: 'light' | 'dark') => {
      tg.colorScheme = s
      ;(events.themeChanged || []).forEach((cb) => cb())
    }
  } else {
    w.WebApp = {
      initData: 'query_id=stub&user=%7B%22id%22%3A1%7D&auth_date=1&hash=stub',
      BackButton: back,
      HapticFeedback: haptic,
      ready: () => undefined,
      close: () => { w.__closed = true },
    }
  }
}

export interface Ctx {
  bot: FakeBot
  platformName: 'telegram' | 'max'
  /** Главная кнопка: нативная (Telegram) или своя внизу (MAX). */
  mainText(): Promise<string>
  mainClick(): Promise<void>
  backClick(): Promise<void>
}

export const test = base.extend<{ ctx: Ctx; scheme: 'light' | 'dark' }>({
  scheme: ['light', { option: true }],
  ctx: async ({ page, scheme }, use, testInfo) => {
    const platformName = testInfo.project.metadata.platform as 'telegram' | 'max'
    const bot = new FakeBot()
    await page.emulateMedia({ colorScheme: scheme })
    await page.addInitScript(sdkStub, { platform: platformName, scheme })
    // SDK из интернета не грузим: заглушка уже на месте.
    await page.route(/telegram\.org|st\.max\.ru/, (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }))
    await page.route(/\/(max\/)?(config|doctors|services|schedule|my_appointment|book|reschedule|cancel|track)(\?|$)/, (r) => bot.handle(r))
    const ctx: Ctx = {
      bot,
      platformName,
      async mainText() {
        if (platformName === 'telegram') {
          return page.evaluate(() => {
            const m = (window as unknown as { __main: { params: { text?: string; is_visible?: boolean } } }).__main
            return m.params.is_visible ? String(m.params.text) : ''
          })
        }
        const btn = page.locator('div.sticky.bottom-0 button')
        return (await btn.count()) ? ((await btn.textContent()) ?? '').trim() : ''
      },
      async mainClick() {
        if (platformName === 'telegram') await page.evaluate(() => (window as unknown as { __main: { click(): void } }).__main.click())
        else await page.locator('div.sticky.bottom-0 button').click()
      },
      async backClick() {
        await page.evaluate(() => (window as unknown as { __back: { click(): void } }).__back.click())
      },
    }
    await use(ctx)
  },
})

export { expect }

export async function fillPatient(page: Page) {
  await page.getByLabel('Фамилия').fill('Смирнова')
  await page.getByLabel('Имя', { exact: true }).fill('Ольга')
  await page.getByLabel('Дата рождения').pressSequentially('14031961')
  await page.getByLabel('Телефон').pressSequentially('9161342331')
}

/** Галочка согласия: нажатие на квадрат, а не на ссылку «условиям клиники» внутри подписи. */
export async function agree(page: Page) {
  await page.getByText('Согласен на обработку персональных данных').click({ position: { x: 4, y: 8 } })
}
