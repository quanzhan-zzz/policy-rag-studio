# Metadata Filter Benchmark

- Generated: 2026-11-23T20:00:00.485087+00:00
- Dataset: policy-official-v1 / test
- Cases: 20
- Embedding: OpenAI-compatible embedding · qwen3.7-text-embedding-flash
- Reranker: BGE reranker · BAAI/bge-reranker-base
- Database: isolated evaluation DB containing official guides plus explicitly labeled outdated and prompt-injection materials

## Results

| Mode | Recall@5 | MRR | nDCG@5 | Document P@5 | Avg candidates | P95 | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| unfiltered | 1.0000 | 0.7725 | 0.8290 | 0.6000 | 31.0 | 2012.1 ms | 0 |
| official_filter | 1.0000 | 0.8417 | 0.8812 | 0.7900 | 24.0 | 820.7 ms | 0 |

## Delta

- Recall@5: +0.0000
- MRR: +0.0692
- nDCG@5: +0.0522
- Document P@5: +0.1900
- Avg candidates: -7.0
- P95: -1191.4 ms

## Failures

- **unfiltered**: none
- **official_filter**: none

## Method

- Both modes use Qwen embedding, Hybrid RRF, the same BGE reranker and Top-5 evaluation.
- Filtered mode applies `region=常州市` and `official_only=true` inside the repository.
- Retrieval Recall/MRR/nDCG require the expected document and section in Top-5.
- Document precision is the share of returned Top-5 chunks from the expected document.
- Document ordering uses retrieval time, effective date and update time, newest first.

## Limitations

- Distractor documents are controlled evaluation fixtures, not production traffic.
- The official filter can hide a legitimate newer policy if its metadata is incomplete.
- Absolute latency includes embedding and rerank network/model costs.
