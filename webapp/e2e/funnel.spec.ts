import { expect, test } from './fixtures'

const steps = (ctx: { bot: { requests: { path: string; body: unknown }[] } }) =>
  ctx.bot.requests.filter((r) => r.path === 'track').map((r) => (r.body as { step: string }).step)

test('воронка: форма отмечает шаги новой записи по одному разу', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова Анна Сергеевна/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await expect(page.getByText('Шаг 3 из 4')).toBeVisible()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await ctx.mainClick()
  await expect(page.getByText('Шаг 4 из 4')).toBeVisible()
  // «Назад» не считается повторным шагом.
  await ctx.backClick()
  await expect(page.getByText('Шаг 3 из 4')).toBeVisible()
  await expect.poll(() => steps(ctx)).toEqual(['open', 'branch', 'doctor', 'time'])
})

test('воронка: перенос записи не отмечается', async ({ page, ctx }) => {
  ctx.bot.active = {
    appointment_id: 'appt-1', branch: 'Профсоюзная', date: '2030-01-10', time: '09:30',
    doctor_id: 'doc-1', doctor_name: 'Иванова Анна Сергеевна', service_id: 'srv-1',
    service_name: 'Консультация офтальмолога', confirmed: false,
  }
  await page.goto('./')
  await page.getByRole('button', { name: 'Перенести на другое время' }).click()
  await expect(page.getByRole('heading', { name: 'Перенос записи' })).toBeVisible()
  await page.waitForTimeout(300)
  expect(steps(ctx)).toEqual([])
})
