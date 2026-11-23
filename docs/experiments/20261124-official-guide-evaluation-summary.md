# 官方办事指南评测总结

- 日期：2026-11-24（Asia/Shanghai）
- 评测集：`policy-official-v1` / `test`
- 样本：20 条人工编写、有明确 gold evidence 的 answerable 问题
- 数据来源：2 份江苏政务服务网官方办事指南
- 评测库：独立 PostgreSQL `policyrag_official_eval`，只包含两份官方指南
- Embedding：`qwen3.7-text-embedding-flash`
- 回答模型与裁判：`glm-5.3-flash`

评测集共 40 条：20 条 development、20 条 test。test split 在确定后冻结，不参与 chunk、RRF、reranker prompt 或查询改写调参。数据集校验和见
[`policy-official-v1.manifest.json`](../../data/eval/policy-official-v1.manifest.json)。

## 检索结果

测试集使用 Hybrid RRF Top-30 候选、Top-5 评测。

| Provider | Recall@5 | MRR | nDCG@5 | P95 | Rerank P95 | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| None / RRF | 0.9000 | 0.7000 | 0.7512 | 332.2 ms | 0.1 ms | 0 |
| Heuristic | 0.9000 | 0.6750 | 0.7312 | 333.1 ms | 1.0 ms | 0 |
| BGE Base | **1.0000** | **0.8417** | **0.8812** | 1102.1 ms | 769.8 ms | 0 |

BGE 消除了纯 RRF 与 Heuristic 的两个 Top-5 漏召回，MRR 相对纯 RRF 提升 `0.1417`。代价是总延迟 P95 从约 `332 ms` 增加到 `1102 ms`；不能只引用质量提升而不说明延迟成本。

完整报告：[`20261124-official-guide-reranker-test.md`](20261124-official-guide-reranker-test.md)。

## 回答质量

回答链路为 `Hybrid + BGE Rerank -> Context Pack -> GLM 带引用回答 -> citation guard`。

| 指标 | 结果 |
| --- | ---: |
| 已生成回答 | 20 / 20 |
| Retrieval Hit@5 | 100.0% |
| 引用召回率 | 100.0% |
| 引用精确率 | 66.8% |
| 无效引用率 | 0.0% |
| Grounding supported | 100.0% |
| Reranker fallbacks | 0 |
| LLM judge 通过率 | 100.0% |
| LLM faithfulness | 5.00 / 5 |
| LLM relevance | 5.00 / 5 |
| LLM completeness | 4.85 / 5 |
| 平均回答耗时 | 6564.2 ms |
| 平均 Token | 1282 |

引用召回率为 100%，但严格引用精确率只有 66.8%，说明回答仍会引用到同一官方章节内并非每一条都直接支持当前结论的片段。不能把“引用编号合法”或“能找到正确章节”表述为引用完全准确。

完整报告：

- [`20261124-official-answer-quality-test.md`](20261124-official-answer-quality-test.md)
- [`20261124-official-answer-quality-test.json`](20261124-official-answer-quality-test.json)
- [20 条人工复核工作表](20261124-official-answer-quality-test-review.md)

## 结论与限制

- 当前 test split 上 BGE 的 Recall@5 达到 100%，但这只是 20 条人工编写问题，不代表真实用户流量。
- 引用精确率仍是主要质量缺口，后续由 citation support verifier 与拒答机制处理。
- LLM 裁判与回答模型相同，存在自评偏差；20 条人工复核尚未完成，因此 `100%` 不能作为独立质量结论。
- 外部模型调用金额尚未计量，BGE 的 CPU 计算和延迟成本也未货币化。
- 评测问题覆盖部门、地点、对象、条件、材料、流程、时限、收费、结果、法律依据、FAQ 和咨询电话，但没有覆盖不可回答、冲突版本或提示词注入；这些由后续安全评测处理。

## 复现命令

```bash
# 独立官方评测库
docker compose exec -T db dropdb --if-exists -U policyrag policyrag_official_eval
docker compose exec -T db createdb -U policyrag policyrag_official_eval
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_official_eval' \
  STORE_BACKEND=postgres uv run alembic upgrade head
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_official_eval' \
  STORE_BACKEND=postgres uv run python - <<'PY'
import asyncio
from app.config import get_settings
from app.db.postgres import PostgresStore

async def main():
    store = await PostgresStore.create(
        get_settings().database_url,
        seed_demo_data=False,
        seed_official_data=True,
    )
    await store.close()

asyncio.run(main())
PY

# 真实 Qwen Embedding + 三组 Reranker
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_official_eval' \
  STORE_BACKEND=postgres uv run python -m app.experiments.reranker_benchmark \
  --providers none,heuristic,bge \
  --dataset policy-official-v1 \
  --split test \
  --output docs/experiments/20261124-official-guide-reranker-test.md

# 真实 Embedding + BGE + GLM answer + GLM judge
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_official_eval' \
  STORE_BACKEND=postgres RERANKER_PROVIDER=bge \
  BGE_RERANKER_MODEL=BAAI/bge-reranker-base \
  uv run python -m app.experiments.answer_quality \
  --dataset policy-official-v1 \
  --split test \
  --concurrency 2 \
  --review-size 20 \
  --output docs/experiments/20261124-official-answer-quality-test.md
```
