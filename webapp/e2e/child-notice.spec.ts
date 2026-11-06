import { agree, expect, fillPatient, test } from './fixtures'

async function toPatient(page: import('@playwright/test').Page, ctx: import('./fixtures').Ctx) {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await ctx.mainClick()
}

test('запись ребёнка: условия приёма и обязательная галочка', async ({ page, ctx }) => {
  await toPatient(page, ctx)
  await fillPatient(page, '15032020')
  await agree(page)
  const notice = page.getByRole('region', { name: 'Приём ребёнка до 18 лет' })
  await expect(notice).toBeVisible()
  await expect(notice.getByText('паспорт законного представителя.')).toBeVisible()
  await ctx.mainClick()
  await expect(page.getByText('Отметьте, что ознакомились с условиями приёма ребёнка')).toBeVisible()
  expect(ctx.bot.requests.some((r) => r.path === 'book')).toBe(false)
  await page.getByText('Я ознакомлен(а) с условиями приёма ребёнка').click()
  await ctx.mainClick()
  await expect(page.getByRole('heading', { name: /Вы записаны/ })).toBeVisible()
  const book = ctx.bot.requests.find((r) => r.path === 'book')!.body as Record<string, unknown>
  expect(book.guardian_ack).toBe(true)
})

test('взрослый пациент — без блока о приёме ребёнка', async ({ page, ctx }) => {
  await toPatient(page, ctx)
  await fillPatient(page)
  await expect(page.getByText('Приём ребёнка до 18 лет')).toHaveCount(0)
  await agree(page)
  await ctx.mainClick()
  await expect(page.getByRole('heading', { name: /Вы записаны/ })).toBeVisible()
  const book = ctx.bot.requests.find((r) => r.path === 'book')!.body as Record<string, unknown>
  expect(book.guardian_ack).toBe(false)
})
