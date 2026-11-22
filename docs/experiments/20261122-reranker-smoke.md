# Reranker Comparison

- Generated: 2026-11-22T08:19:52.420106+00:00
- Dataset cases: 10
- Dataset source: `app/services/seed.py::EVALUATION_CASES`
- Strategy: Hybrid RRF + Top-30 candidate reranking + Top-5 evaluation

## Results

| Provider | Recall@5 | MRR | nDCG@5 | P95 | ΔMRR vs baseline | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic · lexical + rank blend | 1.0000 | 0.7033 | 0.7748 | 289.5 ms | +0.0000 | 0 |
| none · fused order | 1.0000 | 0.7117 | 0.7818 | 289.0 ms | +0.0083 | 0 |

## Failures

- **heuristic · lexical + rank blend**: none
- **none · fused order**: none

## Limitations

- This is the internal 10-case demonstration set, not the final 150-case benchmark.
- Token usage and monetary cost are not yet recorded by the shared LLM provider.
- A non-zero fallback count means reranker errors affected the measured result.
