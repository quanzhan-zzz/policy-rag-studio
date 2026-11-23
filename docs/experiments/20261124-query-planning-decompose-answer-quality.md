# Answer Quality Report

- Generated: 2026-11-23T20:47:41.065322+00:00
- Dataset: policy-official-v1 / test
- Dataset source: `data/eval/policy-official-v1.jsonl`
- Cases: 20
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base
- Answer model: OpenAI-compatible chat · glm-5.3-flash
- Query planning: decompose
- Judge model: OpenAI-compatible chat · glm-5.3-flash
- Human review: 20-case worksheet generated; pending manual completion
- Path: Hybrid + Rerank -> Context Pack -> answer -> citation metrics/judge

## Summary

| Metric | Value |
| --- | ---: |
| Answered | 20 / 20 |
| Retrieval Hit@5 | 100.0% |
| Citation precision | 65.8% |
| Citation recall | 100.0% |
| Invalid citation rate | 0.0% |
| Grounding supported | 100.0% |
| Reranker fallbacks | 0 |
| LLM judge pass rate | 100.0% |
| LLM faithfulness (1-5) | 5.00 |
| LLM relevance (1-5) | 5.00 |
| LLM completeness (1-5) | 4.80 |
| Avg answer latency | 12170.6 ms |
| Avg tokens | 1218 |

## Per-case results

| Case | Hit@5 | Cite P | Cite R | Grounding | F/R/C | Pass |
| --- | :---: | ---: | ---: | --- | --- | :---: |
| `official-company-02` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-company-04` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-06` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-08` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `official-company-10` | ✓ | 1.00 | 1 | supported | 5/5/4 | ✓ |
| `official-company-12` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-14` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-16` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `official-company-18` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-company-20` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-company-22` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-24` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-02` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `official-welfare-04` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-06` | ✓ | 1.00 | 1 | supported | 5/5/4 | ✓ |
| `official-welfare-08` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-10` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-12` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-14` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-16` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |

## Failures and warnings

- none

## Method

- Citation precision = cited sources matching the gold document + heading / all valid cited sources.
- Citation recall = 1 when at least one gold source is cited, otherwise 0 (per case).
- Grounding status comes from the production citation guard.
- Reranker fallbacks are read from the persisted retrieval Trace.
- The LLM judge sees the same evidence pack as the answer model, with faithfulness, relevance and completeness scored 1-5.
- The grader is the configured chat provider; self-evaluation bias is possible.

## Limitations

- The dataset contains hand-authored questions over official guides (20 cases); it is not observed production traffic.
- The judge is the same model family as the answer model. Cross-model judging is recommended.
- A 20-case human review sheet is generated next to this report; fill it before citing results.
- Token counts come from the provider response; monetary cost is not yet recorded.
