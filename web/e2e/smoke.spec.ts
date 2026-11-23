import { expect, test } from '@playwright/test'

test('workbench renders and opens strategy comparison', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: /PolicyRAG/ })).toBeVisible()
  await page.getByRole('link', { name: /检索/ }).click()
  await expect(page.getByRole('heading', { level: 2, name: /检索对比/ })).toBeVisible()
})

test('documents distinguish official sources from demo data', async ({ page }) => {
  await page.goto('/documents')
  await expect(page.getByText('江苏政务服务网·常州法人服务').first()).toBeVisible()
  await expect(page.getByRole('link', { name: /官方来源/ }).first()).toBeVisible()
  await expect(page.getByText('演示数据').first()).toBeVisible()
})

test('upload is queued and reaches the ready state', async ({ page }) => {
  const title = `e2e-async-${Date.now()}`
  await page.goto('/documents')
  await page.locator('input[type="file"]').setInputFiles({
    name: `${title}.md`,
    mimeType: 'text/markdown',
    buffer: Buffer.from(
      `# ${title}\n\n一、适用范围\n用于端到端异步索引测试。\n\n二、办理流程\n提交材料后等待审核。`,
    ),
  })

  const row = page.getByRole('row', { name: new RegExp(title) })
  await expect(row).toBeVisible()
  await expect(row.getByText('索引完成')).toBeVisible({ timeout: 20_000 })
  await expect(row.locator('td').nth(2)).toHaveText(/^[1-9]\d*$/)
})


test('evaluation page records the active reranker', async ({ page }) => {
  await page.goto('/evaluation')
  await expect(page.getByText(/Reranker：heuristic/i)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('完整指标账本')).toBeVisible()
})
