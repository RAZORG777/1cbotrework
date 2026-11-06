import { agree, dayFromToday, expect, fillPatient, test } from './fixtures'

test('запрет онлайн-записи: вместо филиалов — звонок в колл-центр', async ({ page, ctx }) => {
  ctx.bot.blocked = true
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Онлайн-запись недоступна' })).toBeVisible()
  const call = page.getByRole('link', { name: '8 (800) 301-01-67' })
  await expect(call).toHaveAttribute('href', 'tel:88003010167')
  await expect(page.getByRole('button', { name: /Профсоюзная/ })).toHaveCount(0)
})

test('запрет появился во время записи — сообщение с телефоном, запись не создана', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await ctx.mainClick()
  await fillPatient(page)
  await agree(page)
  ctx.bot.nextBookError = { status: 200, body: { status: 'error', error: 'BOOKING_BLOCKED', message: 'недоступна' } }
  await ctx.mainClick()
  await expect(page.getByText('Онлайн-запись для вас сейчас недоступна')).toBeVisible()
  await expect(page.getByRole('link', { name: '8 (800) 301-01-67' }).first()).toBeVisible()
  expect(ctx.bot.active).toBeNull()
})

test('запрет при активной записи: запись видна, отменить можно', async ({ page, ctx }) => {
  ctx.bot.blocked = true
  ctx.bot.active = {
    appointment_id: 'appt-1', branch: 'Профсоюзная', date: dayFromToday(1), time: '09:30',
    doctor_id: 'doc-1', doctor_name: 'Иванова Анна Сергеевна', service_id: 'srv-1',
    service_name: 'Консультация офтальмолога', confirmed: false,
  }
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Моя запись' })).toBeVisible()
  await expect(page.getByText('Иванова Анна Сергеевна')).toBeVisible()
  await expect(page.getByRole('button', { name: /Отменить/ }).first()).toBeVisible()
})
