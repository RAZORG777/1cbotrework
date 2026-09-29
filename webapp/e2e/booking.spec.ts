import { dayFromToday, expect, fillPatient, test, agree } from './fixtures'

test('запись по врачу: филиал → врач → услуга → время → пациент → «Вы записаны»', async ({ page, ctx }) => {
  await page.goto('./')
  await expect(page.getByText('Шаг 1 из 4')).toBeVisible()
  await page.getByRole('button', { name: /Профсоюзная/ }).click()

  await expect(page.getByText('Шаг 2 из 4')).toBeVisible()
  await page.getByRole('button', { name: /Иванова Анна Сергеевна/ }).click()
  await expect(page.getByRole('heading', { name: 'Выбор услуги' })).toBeVisible()
  await expect(page.getByText('Повторный приём')).toBeVisible()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()

  await expect(page.getByText('Шаг 3 из 4')).toBeVisible()
  await expect.poll(() => ctx.mainText()).toBe('Выберите время')
  await expect(page.getByText('Утро')).toBeVisible()
  await page.getByRole('button', { name: '14:30', exact: true }).click()
  await expect.poll(() => ctx.mainText()).toMatch(/^Далее · .+, 14:30$/)
  await ctx.mainClick()

  await expect(page.getByText('Шаг 4 из 4')).toBeVisible()
  await fillPatient(page)
  await ctx.mainClick()
  // Без согласия — ошибка у галочки, запрос не уходит.
  await expect(page.getByText('Без согласия запись невозможна')).toBeVisible()
  expect(ctx.bot.requests.some((r) => r.path === 'book')).toBe(false)
  await agree(page)
  await ctx.mainClick()

  await expect(page.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
  await expect(page.getByText('Смирнова Ольга')).toBeVisible()
  const book = ctx.bot.requests.find((r) => r.path === 'book')!.body as Record<string, unknown>
  expect(book).toMatchObject({
    branch: 'Профсоюзная',
    doctor_id: 'doc-1',
    service_id: 'srv-1',
    date: dayFromToday(1),
    time: '14:30',
    pd_consent: true,
    send_notifications: true,
    patient: { last_name: 'Смирнова', first_name: 'Ольга', birth_date: '14.03.1961', phone: '+79161342331' },
  })
  await expect.poll(() => ctx.mainText()).toBe('Готово')
})

test('запись по услуге: услуга → врач из тех, кто её оказывает', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Новые Ватутинки/ }).click()
  await page.getByRole('tab', { name: 'Услуги' }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await expect(page.getByRole('heading', { name: 'Кто примет?' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Петров/ })).toBeVisible()
  await page.getByRole('button', { name: /Петров/ }).click()
  await expect(page.getByText('Шаг 3 из 4')).toBeVisible()
  await expect(page.getByText('Петров М. О.')).toBeVisible()
  expect(ctx.bot.requests.filter((r) => r.path === 'services').length).toBeGreaterThanOrEqual(2)
})

test('«Назад» мессенджера и сохранение выбора', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '11:00', exact: true }).click()
  await ctx.mainClick()
  await page.getByLabel('Фамилия').fill('Смирнова')
  await ctx.backClick()
  await expect(page.getByText('Шаг 3 из 4')).toBeVisible()
  await expect(page.getByRole('button', { name: '11:00', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await ctx.mainClick()
  await expect(page.getByLabel('Фамилия')).toHaveValue('Смирнова')
})

test('сохранённый пациент подставляется при следующей записи', async ({ page, ctx }) => {
  await page.goto('./')
  await page.getByRole('button', { name: /Профсоюзная/ }).click()
  await page.getByRole('button', { name: /Иванова/ }).click()
  await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
  await page.getByRole('button', { name: '09:30', exact: true }).click()
  await ctx.mainClick()
  await fillPatient(page)
  await agree(page)
  await ctx.mainClick()
  await expect(page.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
  const stored = await page.evaluate(() => localStorage.getItem('yasno_patients_v2'))
  expect(JSON.parse(stored!)[0]).toMatchObject({ key: 'me', label: 'Я', last_name: 'Смирнова' })
})
