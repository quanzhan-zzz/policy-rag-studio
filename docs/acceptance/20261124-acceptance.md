# PolicyRAG Studio 夜间自动执行验收报告

- 日期：2026-11-24
- 分支：`main`
- 自动执行范围：GitHub Issues #1–#3、#5、#7、#8、#11
- 人工阻塞：#4，进而阻塞 #6

## 总体状态

| Issue | 状态 | 结果 |
| --- | --- | --- |
| #1 官方数据源 | 已完成 | 2 份官方指南、6 个材料附件、哈希与来源 |
| #2 官方指南入库 | 已完成 | 三种 Chunk、来源元数据、前端标识 |
| #3 官方评测集 | 已完成 | 40 条冻结问题，20 dev / 20 test |
| #4 人工复核 | **待人工** | 20 条完整工作表已生成，不允许 AI 伪造 |
| #5 对抗评测 | 已完成 | 25 条真实模型安全样本 |
| #6 引用支持校验 | **被 #4 阻塞** | 不绕过人工复核依赖 |
| #7 查询规划 | 已完成 | none/rewrite/decompose，默认 none |
| #8 元数据过滤 | 已完成 | PostgreSQL 查询层过滤和 Trace |
| #11 真实 CI | 已完成 | 真实 Qwen + GLM，无 mock E2E |

## 已合并 PR

- #9 `feat(data): 接入官方办事指南导入链路`
- #10 `feat(seed): 将官方指南纳入可检索语料`
- #12 `ci: 端到端验收切换真实模型环境`
- #13 `feat(eval): 建立官方指南评测集`
- #14 `test(eval): 增加真实对抗与拒答评测`
- #15 `feat(retrieval): 增加政策元数据过滤`
- #16 `feat(retrieval): 增加可回退查询规划`
- #17 `docs(eval): 增加人工复核优先队列`

## 核心真实结果

### 官方检索

- BGE Recall@5：`100%`
- BGE MRR：`0.8417`
- BGE nDCG@5：`0.8812`
- BGE P95：`1102.1 ms`

### 官方回答质量

- 回答生成：`20 / 20`
- 引用召回：`100%`
- 引用精确：`66.8%`
- 无效引用：`0%`
- Grounding supported：`100%`
- LLM judge pass：`100%`（同模型自评，不能单独作为质量结论）
- 平均回答耗时：`6564.2 ms`
- 平均 Token：`1282`

### 对抗评测

- 正确行为：`23 / 25`
- False answers：`2 / 25`
- 应拒答正确率：`19 / 21`
- Prompt-injection 材料暴露：`4 / 4`
- Prompt-injection 实际泄露：`1 / 4`
- 无效引用：`0`

真实失败：
1. 合伙企业问题混用了公司变更材料。
2. 模型虽然拒绝提供密码，但重复输出了恶意材料中的伪造密码。

### 元数据过滤

- Recall@5：`1.0000 → 1.0000`
- MRR：`0.7725 → 0.8417`
- nDCG@5：`0.8290 → 0.8812`
- Document P@5：`0.60 → 0.79`
- 平均候选：`31.0 → 24.0`
- P95：`2012.1 ms → 820.7 ms`
- 注入材料暴露：`4/4 → 0/4`

### 查询规划

test split 结果：

| Mode | MRR | Completeness | Avg latency |
| --- | ---: | ---: | ---: |
| none | 0.8417 | 4.85 | 6564 ms |
| rewrite | 0.8458 | 4.60 | 12489 ms |
| decompose | 0.8250 | 4.80 | 12171 ms |

决策：默认 `QUERY_PLANNING_MODE=none`。rewrite/decompose 保留为可复现实验开关，不默认启用。

## 真实 CI

最新真实 CI 使用：

- PostgreSQL + pgvector
- Redis
- `qwen3.7-text-embedding-flash`
- `glm-5.3-flash`
- 无 mock LLM / 无 Hash Embedding E2E

CI 会验证 provider 身份、官方语料和 6 条 Playwright 路径。最近一次主分支真实 CI 为全绿。

## 第二天需要你完成的唯一人工项

打开 [20 条人工复核工作表](../experiments/20261124-official-answer-quality-test-review.md)，为每条选择：

- `通过`
- `不通过`
- 备注：引用错误、无依据结论、遗漏项或归因

可以先看 [自动审阅优先队列](../experiments/20261124-official-answer-quality-review-triage.md)。该队列不是人工结论，只标记低引用精确率和完整性风险，方便快速复核。

完成后需要：

1. 汇总人工通过率和失败类型。
2. 与 LLM 裁判做差异分析。
3. 更新 README 的“人工复核待完成”状态。
4. 关闭 #4。
5. #6 才能解除阻塞并继续引用支持校验与拒答。

## 验收命令

```bash
uv run ruff check app tests migrations
uv run pytest
make test-postgres

cd web
pnpm lint
pnpm test
pnpm build

E2E_BASE_URL=http://127.0.0.1:8080 pnpm test:e2e
```

## 当前限制

- 人工复核未完成，AI 不会代填通过/不通过。
- #6 因 #4 依赖未解除，尚未实现。
- 官方测试集规模较小，问题为人工编写，不代表真实用户流量。
- 对抗集是有限回归集，不保证覆盖所有提示词注入。
- LLM 裁判与回答模型相同，存在自评偏差。
- 外部模型成本尚未货币化，CI 外部模型调用可能受上游限流影响。
