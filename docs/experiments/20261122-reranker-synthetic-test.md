# Reranker Comparison

- Generated: 2026-11-22T08:49:04.515792+00:00
- Dataset: policy-synthetic-v1 / test
- Dataset cases: 38
- Dataset source: `data/eval/policy-synthetic-v1.jsonl`
- Strategy: Hybrid RRF + Top-30 candidate reranking + Top-5 evaluation

## Results

| Provider | Recall@5 | MRR | nDCG@5 | P95 | ΔMRR vs baseline | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic · lexical + rank blend | 0.9474 | 0.6447 | 0.7203 | 1210.8 ms | +0.0000 | 0 |
| none · fused order | 0.9474 | 0.6390 | 0.7171 | 1210.5 ms | -0.0057 | 0 |

## Failures

- **heuristic · lexical + rank blend**: synthetic-04-06, synthetic-04-07
- **none · fused order**: synthetic-04-06, synthetic-04-07

## Ranking Weak Spots

### heuristic · lexical + rank blend

- `synthetic-04-06` miss — 个体工商户注册的申请步骤是什么？
- `synthetic-04-07` miss — 请问个体工商户注册在申请步骤方面有哪些规定？
- `synthetic-02-06` rank 4 — 个体工商户设立的办理条件是什么？
- `synthetic-02-07` rank 4 — 请问个体工商户设立在办理条件方面有哪些规定？
- `synthetic-05-07` rank 4 — 请问个体工商户登记补正在审核期限方面有哪些规定？

### none · fused order

- `synthetic-04-06` miss — 个体工商户注册的申请步骤是什么？
- `synthetic-04-07` miss — 请问个体工商户注册在申请步骤方面有哪些规定？
- `synthetic-02-07` rank 5 — 请问个体工商户设立在办理条件方面有哪些规定？
- `synthetic-02-06` rank 4 — 个体工商户设立的办理条件是什么？
- `synthetic-09-07` rank 4 — 请问租房补贴申请在申请资格方面有哪些规定？


## Limitations

- This is a synthetic policy retrieval set, not observed production traffic.
- Token usage and monetary cost are not yet recorded by the shared LLM provider.
- A non-zero fallback count means reranker errors affected the measured result.
