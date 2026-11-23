# Query Planning Benchmark

- Generated: 2026-11-23T20:41:33.364610+00:00
- Split: test
- Official answerable cases: 20
- Multi-condition cases: 6
- Planner model: OpenAI-compatible chat · glm-5.3-flash
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base

## Official answerable set

| Mode | Recall@5 | MRR | nDCG@5 | Planner P95 | Retrieval P95 | Avg planner tokens | Avg queries | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 1.0000 | 0.8417 | 0.8812 | 0.0 ms | 964.4 ms | 0.0 | 1.00 | 0 |
| rewrite | 1.0000 | 0.8458 | 0.8846 | 4556.0 ms | 6303.0 ms | 275.5 | 2.00 | 0 |
| decompose | 1.0000 | 0.8250 | 0.8693 | 4444.2 ms | 9398.4 ms | 277.7 | 3.85 | 0 |

## Multi-condition coverage

| Mode | Section coverage | Full coverage | Planner P95 | Retrieval P95 | Avg planner tokens | Avg queries | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 0.8182 | 0.6667 | 0.0 ms | 1112.4 ms | 0.0 | 1.00 | 0 |
| rewrite | 0.8182 | 0.6667 | 4578.4 ms | 6317.5 ms | 280.8 | 2.00 | 0 |
| decompose | 0.7273 | 0.5000 | 5487.4 ms | 9443.3 ms | 276.0 | 4.00 | 0 |

## Failures

### Official · none

- none

### Official · rewrite

- none

### Official · decompose

- none

### Multi-condition · none

- multi-04: 部门信息, multi-08: 部门信息

### Multi-condition · rewrite

- multi-04: 部门信息, multi-08: 部门信息

### Multi-condition · decompose

- multi-04: 部门信息, multi-06: 办理时限, multi-08: 部门信息

## Multi-condition samples

| Case | Mode | Queries | Covered | Missing |
| --- | --- | ---: | --- | --- |
| `multi-02` | none | 1 | 办理材料, 办理流程 | — |
| `multi-04` | none | 1 | 受理标准 | 部门信息 |
| `multi-06` | none | 1 | 法律依据, 办理时限 | — |
| `multi-08` | none | 1 | 窗口办理 | 部门信息 |
| `multi-10` | none | 1 | 办理时限 | — |
| `multi-12` | none | 1 | 法律依据, 部门信息 | — |
| `multi-02` | rewrite | 2 | 办理材料, 办理流程 | — |
| `multi-04` | rewrite | 2 | 受理标准 | 部门信息 |
| `multi-06` | rewrite | 2 | 法律依据, 办理时限 | — |
| `multi-08` | rewrite | 2 | 窗口办理 | 部门信息 |
| `multi-10` | rewrite | 2 | 办理时限 | — |
| `multi-12` | rewrite | 2 | 法律依据, 部门信息 | — |
| `multi-02` | decompose | 4 | 办理材料, 办理流程 | — |
| `multi-04` | decompose | 4 | 受理标准 | 部门信息 |
| `multi-06` | decompose | 4 | 法律依据 | 办理时限 |
| `multi-08` | decompose | 4 | 窗口办理 | 部门信息 |
| `multi-10` | decompose | 4 | 办理时限 | — |
| `multi-12` | decompose | 4 | 法律依据, 部门信息 | — |

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
