# Query Planning Benchmark

- Generated: 2026-11-23T20:34:46.851514+00:00
- Split: dev
- Official answerable cases: 20
- Multi-condition cases: 6
- Planner model: OpenAI-compatible chat · glm-5.3-flash
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base

## Official answerable set

| Mode | Recall@5 | MRR | nDCG@5 | Planner P95 | Retrieval P95 | Avg planner tokens | Avg queries | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 1.0000 | 0.8125 | 0.8592 | 0.0 ms | 1205.2 ms | 0.0 | 1.00 | 0 |
| rewrite | 0.9500 | 0.7875 | 0.8281 | 4799.3 ms | 6542.3 ms | 255.7 | 1.95 | 1 |
| decompose | 0.9500 | 0.7933 | 0.8324 | 4377.4 ms | 8011.7 ms | 271.6 | 3.55 | 0 |

## Multi-condition coverage

| Mode | Section coverage | Full coverage | Planner P95 | Retrieval P95 | Avg planner tokens | Avg queries | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 0.8182 | 0.6667 | 0.0 ms | 1792.5 ms | 0.0 | 1.00 | 0 |
| rewrite | 0.9091 | 0.8333 | 4229.0 ms | 6352.3 ms | 284.5 | 2.00 | 0 |
| decompose | 0.8182 | 0.6667 | 6841.9 ms | 10450.8 ms | 276.0 | 4.00 | 0 |

## Failures

### Official · none

- none

### Official · rewrite

- official-company-01

### Official · decompose

- official-company-01

### Multi-condition · none

- multi-05: 审批结果, multi-11: 咨询投诉

### Multi-condition · rewrite

- multi-05: 审批结果

### Multi-condition · decompose

- multi-05: 审批结果, multi-11: 咨询投诉

## Multi-condition samples

| Case | Mode | Queries | Covered | Missing |
| --- | --- | ---: | --- | --- |
| `multi-01` | none | 1 | 办理材料, 办理时限 | — |
| `multi-03` | none | 1 | 窗口办理 | — |
| `multi-05` | none | 1 | 收费情况 | 审批结果 |
| `multi-07` | none | 1 | 办理材料, 办理时限 | — |
| `multi-09` | none | 1 | 受理标准, 基本信息 | — |
| `multi-11` | none | 1 | 收费情况 | 咨询投诉 |
| `multi-01` | rewrite | 2 | 办理材料, 办理时限 | — |
| `multi-03` | rewrite | 2 | 窗口办理 | — |
| `multi-05` | rewrite | 2 | 收费情况 | 审批结果 |
| `multi-07` | rewrite | 2 | 办理材料, 办理时限 | — |
| `multi-09` | rewrite | 2 | 受理标准, 基本信息 | — |
| `multi-11` | rewrite | 2 | 收费情况, 咨询投诉 | — |
| `multi-01` | decompose | 4 | 办理材料, 办理时限 | — |
| `multi-03` | decompose | 4 | 窗口办理 | — |
| `multi-05` | decompose | 4 | 收费情况 | 审批结果 |
| `multi-07` | decompose | 4 | 办理材料, 办理时限 | — |
| `multi-09` | decompose | 4 | 受理标准, 基本信息 | — |
| `multi-11` | decompose | 4 | 收费情况 | 咨询投诉 |

## Method

- `none` uses the original query with the production Hybrid + BGE path.
- `rewrite` uses one LLM-rewritten policy query.
- `decompose` runs a rewritten broad query plus limited subqueries, then RRF-fuses Top candidates.
- Planner timeout or invalid JSON falls back to the original query.
- Development split may be used for prompt iteration; the test split is final-only.

## Limitations

- Multi-condition questions are hand-authored and small.
- Query planning adds LLM latency and token cost even when retrieval does not improve.
- BGE reranking makes answer latency higher than the planner-only latency.
