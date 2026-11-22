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

## `smoke`

The original 10 hand-written cases remain in `app/services/seed.py::EVALUATION_CASES` for fast
smoke checks and backward compatibility.
