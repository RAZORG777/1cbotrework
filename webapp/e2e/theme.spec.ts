import { expect, test } from './fixtures'

test('переключатель оформления: вручную и обратно «Авто», выбор запоминается', async ({ page, ctx }) => {
  void ctx
  await page.goto('./')
  const html = page.locator('html')
  await expect(html).toHaveAttribute('data-theme', 'light')
  await page.getByRole('radio', { name: 'Тёмная' }).click()
  await expect(html).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('radio', { name: 'Тёмная' })).toHaveAttribute('aria-checked', 'true')

  await page.reload()
  await expect(page.getByText('Шаг 1 из 4')).toBeVisible()
  await expect(html).toHaveAttribute('data-theme', 'dark')

  await page.getByRole('radio', { name: 'Авто' }).click()
  await expect(html).toHaveAttribute('data-theme', 'light')
})
