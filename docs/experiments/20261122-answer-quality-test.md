# Answer Quality Report

- Generated: 2026-11-22T16:15:14.271032+00:00
- Dataset: policy-synthetic-v1 / test
- Cases: 38
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base
- Answer model: OpenAI-compatible chat · glm-5.3-flash
- Judge model: OpenAI-compatible chat · glm-5.3-flash
- Human review: 20-case worksheet generated; pending manual completion
- Path: Hybrid + Rerank -> Context Pack -> answer -> citation metrics/judge

## Summary

| Metric | Value |
| --- | ---: |
| Answered | 38 / 38 |
| Retrieval Hit@5 | 100.0% |
| Citation precision | 34.0% |
| Citation recall | 100.0% |
| Invalid citation rate | 0.0% |
| Grounding supported | 100.0% |
| Reranker fallbacks | 0 |
| LLM judge pass rate | 100.0% |
| LLM faithfulness (1-5) | 5.00 |
| LLM relevance (1-5) | 4.89 |
| LLM completeness (1-5) | 4.45 |
| Avg answer latency | 9233.9 ms |
| Avg tokens | 1659 |

## Per-case results

| Case | Hit@5 | Cite P | Cite R | Grounding | F/R/C | Pass |
| --- | :---: | ---: | ---: | --- | --- | :---: |
| `synthetic-01-06` | ✓ | 0.20 | 1 | supported | 5/4/3 | ✓ |
| `synthetic-01-07` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-02-06` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-02-07` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-03-06` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-03-07` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-04-06` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-04-07` | ✓ | 0.25 | 1 | supported | 5/4/4 | ✓ |
| `synthetic-05-06` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-05-07` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-06-06` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-06-07` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-07-06` | ✓ | 0.33 | 1 | supported | 5/4/3 | ✓ |
| `synthetic-07-07` | ✓ | 0.50 | 1 | supported | 5/4/3 | ✓ |
| `synthetic-08-06` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-08-07` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-09-06` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-09-07` | ✓ | 0.33 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-10-06` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-10-07` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-11-06` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-11-07` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-12-06` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-12-07` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-13-06` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-13-07` | ✓ | 0.25 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-14-06` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-14-07` | ✓ | 0.50 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-15-06` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-15-07` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-16-06` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-16-07` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-17-06` | ✓ | 0.25 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-17-07` | ✓ | 0.20 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-18-06` | ✓ | 0.33 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-18-07` | ✓ | 0.25 | 1 | supported | 5/5/5 | ✓ |
| `synthetic-19-06` | ✓ | 0.25 | 1 | supported | 5/5/4 | ✓ |
| `synthetic-19-07` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |

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

- The dataset is synthetic and small (38 cases); absolute scores are not production claims.
- The judge is the same model family as the answer model. Cross-model judging is recommended.
- A 20-case human review sheet is generated next to this report; fill it before citing results.
- Token counts come from the provider response; monetary cost is not yet recorded.
