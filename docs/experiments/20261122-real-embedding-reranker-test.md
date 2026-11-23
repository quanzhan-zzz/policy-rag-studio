# Reranker Comparison

- Generated: 2026-11-22T15:09:14.506324+00:00
- Dataset: policy-synthetic-v1 / test
- Dataset cases: 38
- Embedding provider: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Dataset source: `data/eval/policy-synthetic-v1.jsonl`
- Strategy: Hybrid RRF + Top-30 candidate reranking + Top-5 evaluation

## Results

| Provider | Recall@5 | MRR | nDCG@5 | P95 | Rerank P95 | ΔMRR vs baseline | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none · fused order | 0.9474 | 0.6412 | 0.7189 | 1887.1 ms | 0.1 ms | +0.0000 | 0 |
| heuristic · lexical + rank blend | 0.9474 | 0.6447 | 0.7203 | 1887.0 ms | 0.4 ms | +0.0035 | 0 |
| BGE reranker · BAAI/bge-reranker-base | 1.0000 | 0.7833 | 0.8372 | 1990.9 ms | 113.8 ms | +0.1421 | 0 |

## Failures

- **none · fused order**: synthetic-04-06, synthetic-04-07
- **heuristic · lexical + rank blend**: synthetic-04-06, synthetic-04-07
- **BGE reranker · BAAI/bge-reranker-base**: none

## Ranking Weak Spots

### none · fused order

- `synthetic-04-06` miss — 个体工商户注册的申请步骤是什么？
- `synthetic-04-07` miss — 请问个体工商户注册在申请步骤方面有哪些规定？
- `synthetic-02-07` rank 5 — 请问个体工商户设立在办理条件方面有哪些规定？
- `synthetic-02-06` rank 4 — 个体工商户设立的办理条件是什么？
- `synthetic-15-07` rank 4 — 请问企业法定代表人变更登记在变更步骤方面有哪些规定？

### heuristic · lexical + rank blend

- `synthetic-04-06` miss — 个体工商户注册的申请步骤是什么？
- `synthetic-04-07` miss — 请问个体工商户注册在申请步骤方面有哪些规定？
- `synthetic-02-06` rank 4 — 个体工商户设立的办理条件是什么？
- `synthetic-02-07` rank 4 — 请问个体工商户设立在办理条件方面有哪些规定？
- `synthetic-05-07` rank 4 — 请问个体工商户登记补正在审核期限方面有哪些规定？

### BGE reranker · BAAI/bge-reranker-base

- `synthetic-04-06` rank 5 — 个体工商户注册的申请步骤是什么？
- `synthetic-04-07` rank 5 — 请问个体工商户注册在申请步骤方面有哪些规定？
- `synthetic-15-07` rank 5 — 请问企业法定代表人变更登记在变更步骤方面有哪些规定？
- `synthetic-06-06` rank 3 — 个体工商户经营范围的材料与经营场所要求是什么？
- `synthetic-06-07` rank 3 — 请问个体工商户经营范围在材料与经营场所要求方面有哪些规定？


## Limitations

- This is a synthetic policy retrieval set, not observed production traffic.
- Token usage and monetary cost are not yet recorded by the shared LLM provider.
- A non-zero fallback count means reranker errors affected the measured result.
- Local BGE model loading is excluded by a warmup call; API monetary cost is zero, but CPU compute and electricity are not monetized.
