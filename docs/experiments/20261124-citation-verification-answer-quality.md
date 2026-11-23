# Answer Quality Report

- Generated: 2026-11-23T22:01:12.736390+00:00
- Dataset: policy-official-v1 / test
- Dataset source: `data/eval/policy-official-v1.jsonl`
- Cases: 20
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base
- Answer model: OpenAI-compatible chat · GLM-5.3-Flash
- Query planning: none
- Citation verifier: rule
- Judge model: OpenAI-compatible chat · GLM-5.3-Flash
- Human review: 20-case worksheet generated; **not completed**, no human pass/fail is claimed
- Path: Hybrid + Rerank -> Context Pack -> answer -> citation metrics/judge

## Summary

| Metric | Value |
| --- | ---: |
| Answered | 20 / 20 |
| Retrieval Hit@5 | 100.0% |
| Citation precision | 73.3% |
| Citation recall | 100.0% |
| Invalid citation rate | 0.0% |
| Grounding supported | 25.0% |
| Reranker fallbacks | 0 |
| LLM judge pass rate | 95.0% |
| LLM faithfulness (1-5) | 4.75 |
| LLM relevance (1-5) | 4.90 |
| LLM completeness (1-5) | 4.25 |
| Avg answer latency | 5803.1 ms |
| Avg tokens | 1278 |
| Verification P50 | 2.231 ms |
| Verification P95 | 6.477 ms |
| Removed claims | 40 |
| Removed citations | 0 |
| Avg verification tokens | 0.0 |
| Verification abstentions | 0 |
| Verification failures | 0 |

## Per-case results

| Case | Hit@5 | Cite P | Cite R | Grounding | F/R/C | Pass |
| --- | :---: | ---: | ---: | --- | --- | :---: |
| `official-company-02` | ✓ | 0.50 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-04` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-06` | ✓ | 1.00 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-08` | ✓ | 0.33 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-10` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-company-12` | ✓ | 1.00 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-14` | ✓ | 1.00 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-16` | ✓ | 1.00 | 1 | supported | 5/5/4 | ✓ |
| `official-company-18` | ✓ | 0.33 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-company-20` | ✓ | 0.33 | 1 | partially_supported | 5/5/4 | ✓ |
| `official-company-22` | ✓ | 1.00 | 1 | partially_supported | 4/5/4 | ✓ |
| `official-company-24` | ✓ | 0.50 | 1 | partially_supported | 4/4/1 | ✓ |
| `official-welfare-02` | ✓ | 0.50 | 1 | partially_supported | 5/5/4 | ✓ |
| `official-welfare-04` | ✓ | 0.50 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-06` | ✓ | 1.00 | 1 | partially_supported | 5/5/4 | ✓ |
| `official-welfare-08` | ✓ | 1.00 | 1 | supported | 5/5/5 | ✓ |
| `official-welfare-10` | ✓ | 1.00 | 1 | partially_supported | 5/5/5 | ✓ |
| `official-welfare-12` | ✓ | 0.33 | 1 | partially_supported | 5/5/4 | ✓ |
| `official-welfare-14` | ✓ | 1.00 | 1 | partially_supported | 2/4/2 | ✗ |
| `official-welfare-16` | ✓ | 0.33 | 1 | partially_supported | 5/5/3 | ✓ |

## Failures and warnings

- `official-welfare-14` — 公益性岗位补贴的依据涉及哪些法律和条例？ — judge: 回答遗漏了江苏省就业促进条例第七十四条岗位补贴这一核心设定依据，且错误地把条例第七十六条归入就业促进法名下。

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
