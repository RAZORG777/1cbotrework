import { mkdirSync } from 'node:fs'
import type { Page } from '@playwright/test'
import { agree, dayFromToday, expect, fillPatient, test, type Ctx } from './fixtures'

/* SC-004/SC-005: 320/390/430 px × светлая/тёмная — без горизонтальной прокрутки,
   кнопки не меньше 44 px; снимки экранов — для ручной проверки в e2e/screenshots. */

const WIDTHS = [320, 390, 430]
const SCHEMES = ['light', 'dark'] as const
mkdirSync('e2e/screenshots', { recursive: true })

async function check(page: Page, ctx: Ctx, tag: string, step: string) {
  await page.waitForTimeout(700) // дождаться конца анимаций входа
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, `горизонтальная прокрутка на «${step}»`).toBeLessThanOrEqual(0)
  const small = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('button, [role="tab"], [role="radio"]')]
      .filter((el) => !el.classList.contains('sr-only') && el.offsetParent !== null)
      .map((el) => ({ text: (el.textContent || el.getAttribute('aria-label') || '').trim(), r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 2 && (r.height < 44 || r.width < 44))
      .map(({ text, r }) => `${text} ${Math.round(r.width)}×${Math.round(r.height)}`),
  )
  expect(small, `мелкие кнопки на «${step}»`).toEqual([])
  await page.screenshot({ path: `e2e/screenshots/${tag}-${step}.png`, fullPage: true })
  void ctx
}

for (const scheme of SCHEMES) {
  for (const width of WIDTHS) {
    test.describe(`${scheme} ${width}px`, () => {
      test.use({ scheme, viewport: { width, height: 780 } })

      test('путь записи и «Моя запись»', async ({ page, ctx }, info) => {
        const tag = `${info.project.name}-${scheme}-${width}`
        await page.goto('./')
        await expect(page.getByText('Шаг 1 из 4')).toBeVisible()
        await check(page, ctx, tag, '1-filial')

        await page.getByRole('button', { name: /Профсоюзная/ }).click()
        await expect(page.getByRole('button', { name: /Иванова/ })).toBeVisible()
        await check(page, ctx, tag, '2-vrachi')
        await page.getByRole('tab', { name: 'Услуги' }).click()
        await expect(page.getByText('Первичный приём')).toBeVisible()
        await check(page, ctx, tag, '2-uslugi')
        await page.getByRole('tab', { name: 'Врачи' }).click()

        await page.getByRole('button', { name: /Иванова/ }).click()
        await expect(page.getByRole('heading', { name: 'Выбор услуги' })).toBeVisible()
        await check(page, ctx, tag, '2b-usluga-vracha')
        await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()

        await page.getByRole('button', { name: '14:30', exact: true }).click()
        await check(page, ctx, tag, '3-vremya')
        await ctx.mainClick()

        await ctx.mainClick() // пустая форма — ошибки у полей
        await expect(page.getByText(/Проверьте \d+ пол/)).toBeVisible()
        await check(page, ctx, tag, '4-pacient-oshibki')
        await fillPatient(page)
        await agree(page)
        await check(page, ctx, tag, '4-pacient')
        await ctx.mainClick()

        await expect(page.getByRole('heading', { name: 'Вы записаны' })).toBeVisible()
        await check(page, ctx, tag, '5-gotovo')

        await page.getByRole('button', { name: 'Открыть «Мою запись»' }).click()
        await expect(page.getByRole('heading', { name: 'Моя запись' })).toBeVisible()
        await check(page, ctx, tag, '6-moya-zapis')
        await page.getByRole('button', { name: 'Отменить запись' }).click()
        await check(page, ctx, tag, '7-otmena')
      })

      test('загрузка и неделя без мест', async ({ page, ctx }, info) => {
        const tag = `${info.project.name}-${scheme}-${width}`
        ctx.bot.schedule = { [dayFromToday(14)]: ['10:00'] }
        await page.route(/\/schedule/, async (r) => {
          await new Promise((res) => setTimeout(res, 1500))
          await ctx.bot.handle(r)
        })
        await page.goto('./')
        await page.getByRole('button', { name: /Профсоюзная/ }).click()
        await page.getByRole('button', { name: /Иванова/ }).click()
        await page.getByRole('button', { name: /Консультация офтальмолога/ }).click()
        await expect(page.getByText('Ищем свободное время…')).toBeVisible()
        await page.screenshot({ path: `e2e/screenshots/${tag}-3-zagruzka.png` })
        await expect(page.getByRole('button', { name: '10:00', exact: true })).toBeVisible()
        await page.getByRole('button', { name: 'Раньше' }).click()
        await expect(page.getByText('На этой неделе мест нет')).toBeVisible()
        await check(page, ctx, tag, '3-net-mest')
      })
    })
  }
}
