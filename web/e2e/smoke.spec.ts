import { expect, test } from '@playwright/test'

test('workbench renders and opens strategy comparison', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('PolicyRAG')).toBeVisible()
  await page.getByRole('link', { name: /检索对比/ }).click()
  await expect(page.getByRole('heading', { name: /别只看答案/ })).toBeVisible()
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
  await expect(row.getByText('3')).toBeVisible()
})


test('evaluation page records the active reranker', async ({ page }) => {
  await page.goto('/evaluation')
  await expect(page.getByText(/reranker: heuristic/i)).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('完整指标账本')).toBeVisible()
})
