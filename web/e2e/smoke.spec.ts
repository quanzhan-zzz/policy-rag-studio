import { expect, test } from '@playwright/test'

test('workbench renders and opens strategy comparison', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('PolicyRAG')).toBeVisible()
  await page.getByRole('link', { name: /检索对比/ }).click()
  await expect(page.getByRole('heading', { name: /别只看答案/ })).toBeVisible()
})
