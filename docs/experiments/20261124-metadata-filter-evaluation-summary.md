# 政策元数据过滤评测总结

- 日期：2026-11-24（Asia/Shanghai）
- 数据库：独立 PostgreSQL `policyrag_adversarial_eval`
- 语料：2 份官方指南 + 1 份明确标注的旧版冲突材料 + 1 份明确标注的提示词注入材料
- 数据集：`policy-official-v1 / test`（20 条）与 `policy-adversarial-v1 / test`（25 条）
- Embedding：`qwen3.7-text-embedding-flash`
- Reranker：`BAAI/bge-reranker-base`
- 回答模型：`glm-5.3-flash`

## 检索质量

过滤条件：`region=常州市`、`official_only=true`。

| 模式 | Recall@5 | MRR | nDCG@5 | Document P@5 | 平均候选数 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 无过滤 | 1.0000 | 0.7725 | 0.8290 | 0.6000 | 31.0 | 2012.1 ms |
| 官方过滤 | 1.0000 | **0.8417** | **0.8812** | **0.7900** | **24.0** | **820.7 ms** |

Recall 没有变化，但 MRR 提升 `0.0692`，文档级 Precision@5 提升 `0.19`，候选数减少 `7`，P95 降低约 `1191 ms`。这说明过滤价值主要来自减少噪声和排序干扰，而不是“多召回了原本找不到的条款”。

完整报告：[`20261124-metadata-filter-evaluation.md`](20261124-metadata-filter-evaluation.md)。

## 对抗行为影响

同一对抗集在无过滤和官方过滤下的真实模型结果：

| 指标 | 无过滤 | 官方过滤 |
| --- | ---: | ---: |
| 正确行为 | 23 / 25 | 22 / 25 |
| 应拒答正确率 | 19 / 21 | 18 / 21 |
| 注入材料暴露 | 4 / 4 | 0 / 4 |
| Prompt-injection 实际泄露 | 1 / 4 | 0 / 4 |
| 无效引用 | 0 | 0 |

官方过滤排除了旧版与提示词注入材料，消除了观察到的注入泄露，并让冲突版本题全部使用现行官方条款。但它没有自动修复“材料未规定”被模型推断成“明确不需要”的问题；过滤后的失败主要属于这类无依据推断以及相似事项混用。

相关报告：

- [无过滤对抗评测](20261124-adversarial-evaluation.md)
- [官方过滤对抗评测](20261124-adversarial-filtered-evaluation.md)

## 实现边界

- API 接受显式结构化过滤：地区、事项类型、部门、官方来源、生效日期和抓取时间。
- PostgreSQL 在 `all_chunks()`、`dense_scores()` 和计数查询中先过滤再返回，不把全量 Chunk 拉到 Python 后筛选。
- 内存适配器与 PostgreSQL 契约测试使用同一过滤规则。
- Trace 新增 `metadata_filter` 阶段，记录过滤条件、前后候选数和过滤耗时。
- 无匹配结果返回明确错误，不跨地区或跨来源回退。
- 文档按“抓取时间 → 生效日期 → 更新时间”从新到旧排序；缺少可解析生效日期的文档不会通过日期过滤。

## 局限

- 地区、事项类型和生效日期依赖来源元数据质量；元数据缺失时过滤会偏保守。
- 官方来源过滤器适合“只答官方政策”的场景，但不应用于需要引用历史沿革的查询。
- 当前没有多地区真实语料，地区过滤主要验证了排除未标注/其他地区数据的行为。
- 无依据推断仍需由引用支持校验与拒答机制处理，不能依赖元数据过滤解决。

## 复现命令

```bash
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_adversarial_eval' \
  STORE_BACKEND=postgres BGE_RERANKER_MODEL=BAAI/bge-reranker-base \
  uv run python -m app.experiments.metadata_filter_benchmark \
  --dataset policy-official-v1 \
  --split test \
  --top-k 5 \
  --output docs/experiments/20261124-metadata-filter-evaluation.md

DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_adversarial_eval' \
  STORE_BACKEND=postgres RERANKER_PROVIDER=bge \
  BGE_RERANKER_MODEL=BAAI/bge-reranker-base \
  uv run python -m app.experiments.adversarial_eval \
  --concurrency 2 \
  --top-k 5 \
  --official-only \
  --region 常州市 \
  --output docs/experiments/20261124-adversarial-filtered-evaluation.md
```
