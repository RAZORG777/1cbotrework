import { dayFromToday, expect, test, agree } from './fixtures'

const ACTIVE = {
  appointment_id: 'appt-1',
  branch: 'Профсоюзная',
  date: dayFromToday(1),
  time: '09:30',
  doctor_id: 'doc-1',
  doctor_name: 'Иванова Анна Сергеевна',
  service_id: 'srv-1',
  service_name: 'Консультация офтальмолога',
  confirmed: true,
}

test('активная запись открывает «Мою запись» с отметкой подтверждения', async ({ page, ctx }) => {
  ctx.bot.active = { ...ACTIVE }
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Моя запись' })).toBeVisible()
  await expect(page.getByText('Вы подтвердили визит')).toBeVisible()
  await expect(page.getByText('Иванова Анна Сергеевна')).toBeVisible()
})

test('перенос без повторного ввода данных пациента', async ({ page, ctx }) => {
  ctx.bot.active = { ...ACTIVE }
  await page.goto('./')
  await page.getByRole('button', { name: 'Перенести на другое время' }).click()
  await expect(page.getByRole('heading', { name: 'Перенос записи' })).toBeVisible()
  await page.getByRole('button', { name: '15:00', exact: true }).click()
  await expect.poll(() => ctx.mainText()).toMatch(/^Перенести на .+, 15:00$/)
  await ctx.mainClick()
  await expect(page.getByRole('heading', { name: 'Запись перенесена' })).toBeVisible()
  const body = ctx.bot.requests.find((r) => r.path === 'reschedule')!.body as Record<string, unknown>
  expect(body).toMatchObject({ old_appointment_id: 'appt-1', time: '15:00', doctor_id: 'doc-1', pd_consent: false })
  expect(body).not.toHaveProperty('patient')
})

test('отмена подтверждается на странице и предлагает записаться снова', async ({ page, ctx }) => {
  ctx.bot.active = { ...ACTIVE, confirmed: false }
  await page.goto('./')
  await page.getByRole('button', { name: 'Отменить запись' }).click()
  await expect(page.getByRole('heading', { name: /Отменить запись на/ })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: 'Оставить запись' }).click()
  await expect(page.getByRole('button', { name: 'Отменить запись' })).toBeVisible()
  await page.getByRole('button', { name: 'Отменить запись' }).click()
  await page.getByRole('button', { name: 'Да, отменить' }).click()
  await expect(page.getByText('Запись отменена')).toBeVisible()
  expect(ctx.bot.active).toBeNull()
  await page.getByRole('button', { name: 'Записаться снова' }).click()
  await expect(page.getByText('Шаг 1 из 4')).toBeVisible()
})

test('вторая запись ведёт на «Мою запись»', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '09:30', exact: true }).click()
  await ctx.mainClick()
  await page.getByLabel('Фамилия').fill('Смирнова')
  await page.getByLabel('Имя', { exact: true }).fill('Ольга')
  await page.getByLabel('Дата рождения').pressSequentially('14031961')
  await page.getByLabel('Телефон').pressSequentially('9161342331')
  await agree(page)
  ctx.bot.active = { ...ACTIVE }
  ctx.bot.nextBookError = { status: 200, body: { status: 'error', error: 'SECOND_BOOKING_ERROR' } }
  await ctx.mainClick()
  await expect(page.getByRole('heading', { name: 'Моя запись' })).toBeVisible()
})
