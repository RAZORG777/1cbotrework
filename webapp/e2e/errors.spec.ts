import { expect, fillPatient, test, agree } from './fixtures'

async function toPatient(page: import('@playwright/test').Page, ctx: import('./fixtures').Ctx) {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await ctx.mainClick()
  await fillPatient(page)
  await agree(page)
}

test('время заняли: назад на выбор времени, слот недоступен, данные сохранены', async ({ page, ctx }) => {
  await toPatient(page, ctx)
  ctx.bot.nextBookError = { status: 200, body: { status: 'error', error: 'SLOT_TAKEN', message: 'занято' } }
  await ctx.mainClick()
  await expect(page.getByText('Время 14:30 только что заняли')).toBeVisible()
  await expect(page.getByRole('button', { name: '14:30, занято' })).toBeDisabled()
  await expect.poll(() => ctx.mainText()).toBe('Выберите время')
  await page.getByRole('button', { name: '15:00', exact: true }).click()
  await ctx.mainClick()
  await expect(page.getByLabel('Фамилия')).toHaveValue('Смирнова')
})

test('ошибка телефона от сервера — у поля', async ({ page, ctx }) => {
  await toPatient(page, ctx)
  ctx.bot.nextBookError = { status: 422, body: { status: 'error', error: 'BAD_PHONE', message: 'Проверьте номер телефона' } }
  await ctx.mainClick()
  await expect(page.getByText('Проверьте номер телефона')).toBeVisible()
  await expect(page.getByLabel('Телефон')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('Проверьте 1 поле ниже')).toBeVisible()
})

test('сервис недоступен — общее сообщение с телефоном клиники, без текста 1С', async ({ page, ctx }) => {
  await toPatient(page, ctx)
  ctx.bot.nextBookError = { status: 502, body: { status: 'error', error: 'SERVICE_UNAVAILABLE', message: 'Traceback 1С' } }
  await ctx.mainClick()
  await expect(page.getByText('Не удалось записаться')).toBeVisible()
  await expect(page.getByText('8 (800) 301-01-67').first()).toBeVisible()
  await expect(page.getByText('Traceback')).toHaveCount(0)
})

test('ошибки проверки полей до отправки', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await ctx.mainClick()
  await page.getByLabel('Дата рождения').pressSequentially('14032961')
  await ctx.mainClick()
  await expect(page.getByText('Дата в будущем. Формат: ДД.ММ.ГГГГ')).toBeVisible()
  await expect(page.getByText(/Проверьте \d поля? ниже|Проверьте \d полей ниже/)).toBeVisible()
  expect(ctx.bot.requests.some((r) => r.path === 'book')).toBe(false)
})

test('открыто не из бота — экран доступа', async ({ page, ctx }) => {
  ctx.bot.auth = 'OPEN_FROM_BOT'
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Откройте запись через бота клиники' })).toBeVisible()
})

test('сессия устарела — экран доступа', async ({ page, ctx }) => {
  ctx.bot.auth = 'SESSION_EXPIRED'
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Сессия устарела' })).toBeVisible()
})

test('неделя без мест: ближайшая дата', async ({ page, ctx }) => {
  const d = new Date()
  d.setDate(d.getDate() + 14)
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  ctx.bot.schedule = { [iso]: ['10:00'] }
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  // Первая страница со свободным днём открывается сама; назад — неделя без мест.
  await expect(page.getByRole('button', { name: '10:00', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Раньше' }).click()
  await expect(page.getByText('На этой неделе мест нет')).toBeVisible()
  await page.getByRole('button', { name: /Ближайшее:/ }).click()
  await expect(page.getByRole('button', { name: '10:00', exact: true })).toBeVisible()
})
