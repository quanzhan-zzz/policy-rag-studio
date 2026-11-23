# Evaluation Datasets

## `policy-synthetic-v1.jsonl`

- 152 cases total
- 114 `dev` cases
- 38 `test` cases
- 19 policy headings × 8 paraphrases
- Labels point to an existing document and heading pair
- Generated reproducibly by `app/experiments/build_synthetic_eval.py`

The split is fixed during generation:

- Variants `00–05`: development set
- Variants `06–07`: test set

This is a **synthetic retrieval benchmark**, not observed production traffic. It is suitable for
comparing retrieval configurations under a frozen label set, but it does not establish real-user
coverage. Questions are template variants around policy headings, so metrics should be reported with
that limitation.

The test split must not be used to tune chunk sizes, RRF parameters or reranker prompts. Use the
development split for iteration and the test split only for final comparison.

## `policy-official-v1.jsonl`

- 40 hand-written answerable cases from two official JZSWFW guides
- 20 `dev` cases and 20 `test` cases, fixed at creation time
- Each case records target document, target section, gold evidence summary and failure type
- Questions cover departments, service locations, conditions, materials, processes, deadlines,
  fees, results, legal basis, FAQs and contact information
- Labels are validated against the official seed corpus in `tests/test_evaluation_dataset.py`

The test split must not be used to tune chunking, RRF, reranker prompts or query rewriting. Use
`dev` for iteration and run `test` only for final comparisons.

This benchmark uses official materials but its questions are hand-authored; it is not observed
production traffic.

## `smoke`

The original 10 hand-written cases remain in `app/services/seed.py::EVALUATION_CASES` for fast
smoke checks and backward compatibility.
