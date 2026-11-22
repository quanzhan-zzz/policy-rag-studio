import { expect, test } from '@playwright/test'

test('chunk lab exposes all chunking profiles', async ({ page }) => {
  await page.goto('/chunk-lab')
  await expect(page.getByRole('heading', { name: /切片不是预处理/ })).toBeVisible()
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
  await expect(page.getByText(/劳动合同和社保记录/)).toBeVisible()
  await expect(page.getByText('SOURCE REGISTER')).toBeVisible()

  const traceLink = page.getByRole('link', { name: /Trace/ }).first()
  await traceLink.click()
  await expect(page.getByRole('heading', { name: /Trace 检索执行链|每一次排名变化/ })).toBeVisible()
})
