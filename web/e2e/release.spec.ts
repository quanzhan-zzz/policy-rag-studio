import { expect, test } from '@playwright/test'

test('chunk lab exposes all chunking profiles', async ({ page }) => {
  await page.goto('/chunk-lab')
  await expect(page.getByRole('heading', { name: /切片实验/ })).toBeVisible()
  await expect(page.getByText('固定长度', { exact: true })).toBeVisible()
  await expect(page.getByText('标题层级', { exact: true })).toBeVisible()
  await expect(page.getByText('递归切片', { exact: true })).toBeVisible()
})

test('streaming answer and trace complete the evidence loop', async ({ page }) => {
  await page.goto('/retrieval')
  const generate = page.getByRole('button', { name: '生成带引用回答' })
  await expect(generate).toBeVisible({ timeout: 20_000 })
  await generate.click()
  await expect(page.getByText(/首字/)).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('引用登记')).toBeVisible()

  const traceLink = page.locator('main').getByRole('link', { name: 'Trace' }).first()
  await traceLink.click()
  await expect(page.getByRole('heading', { level: 2, name: /执行详情/ })).toBeVisible()
})
