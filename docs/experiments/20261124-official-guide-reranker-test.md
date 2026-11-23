# Reranker Comparison

- Generated: 2026-11-23T19:22:30.954888+00:00
- Dataset: policy-official-v1 / test
- Dataset cases: 20
- Embedding provider: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Dataset source: `data/eval/policy-official-v1.jsonl`
- Strategy: Hybrid RRF + Top-30 candidate reranking + Top-5 evaluation

## Results

| Provider | Recall@5 | MRR | nDCG@5 | P95 | Rerank P95 | ΔMRR vs baseline | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none · fused order | 0.9000 | 0.7000 | 0.7512 | 332.2 ms | 0.1 ms | +0.0000 | 0 |
| heuristic · lexical + rank blend | 0.9000 | 0.6750 | 0.7312 | 333.1 ms | 1.0 ms | -0.0250 | 0 |
| BGE reranker · BAAI/bge-reranker-base | 1.0000 | 0.8417 | 0.8812 | 1102.1 ms | 769.8 ms | +0.1417 | 0 |

## Failures

- **none · fused order**: official-company-20, official-welfare-02
- **heuristic · lexical + rank blend**: official-company-20, official-welfare-02
- **BGE reranker · BAAI/bge-reranker-base**: none

## Ranking Weak Spots

### none · fused order

- `official-company-20` miss — 办理公司变更登记需要缴费吗？
- `official-welfare-02` miss — 用人单位线下申领公益性岗位补贴去哪里办理？
- `official-company-04` rank 3 — 哪些主体可以作为公司变更登记的服务对象？
- `official-welfare-12` rank 3 — 申领公益性岗位补贴和社保补贴是否收费？
- `official-welfare-16` rank 3 — 该补贴申领能否网上办理，必须到现场吗？

### heuristic · lexical + rank blend

- `official-company-20` miss — 办理公司变更登记需要缴费吗？
- `official-welfare-02` miss — 用人单位线下申领公益性岗位补贴去哪里办理？
- `official-welfare-10` rank 4 — 公益性岗位补贴和社保补贴的法定办结时限是多少？
- `official-welfare-12` rank 4 — 申领公益性岗位补贴和社保补贴是否收费？
- `official-company-04` rank 3 — 哪些主体可以作为公司变更登记的服务对象？

### BGE reranker · BAAI/bge-reranker-base

- `official-welfare-02` rank 4 — 用人单位线下申领公益性岗位补贴去哪里办理？
- `official-welfare-10` rank 4 — 公益性岗位补贴和社保补贴的法定办结时限是多少？
- `official-welfare-12` rank 3 — 申领公益性岗位补贴和社保补贴是否收费？
- `official-company-18` rank 2 — 公司变更登记承诺几个工作日办结？
- `official-company-20` rank 2 — 办理公司变更登记需要缴费吗？


## Limitations

- Questions are hand-authored over official guides, not observed production traffic.
- Token usage and monetary cost are not yet recorded by the shared LLM provider.
- A non-zero fallback count means reranker errors affected the measured result.
- Local BGE model loading is excluded by a warmup call; API monetary cost is zero, but CPU compute and electricity are not monetized.
