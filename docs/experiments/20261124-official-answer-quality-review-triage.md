# Official Answer Quality — Automated Review Triage

> This file is an automated triage aid, not human review. It does not complete issue #4.

- Source: `20261124-official-answer-quality-test.json`
- Cases: 20
- Human decisions remain blank in `20261124-official-answer-quality-test-review.md`.

## Priority summary

| Case | Cite precision | Completeness | Extra cited docs | Triage |
| --- | ---: | ---: | --- | --- |
| `official-company-02` | 1.00 | 4 | — | 检查完整性漏项 |
| `official-company-04` | 1.00 | 5 | — | 正常通读 |
| `official-company-06` | 0.50 | 5 | — | 检查过度引用 |
| `official-company-08` | 0.33 | 5 | — | 检查过度引用 |
| `official-company-10` | 1.00 | 5 | — | 正常通读 |
| `official-company-12` | 1.00 | 4 | — | 检查完整性漏项 |
| `official-company-14` | 1.00 | 5 | — | 正常通读 |
| `official-company-16` | 0.50 | 4 | — | 检查过度引用；检查完整性漏项 |
| `official-company-18` | 0.50 | 5 | — | 检查过度引用 |
| `official-company-20` | 0.33 | 5 | — | 检查过度引用 |
| `official-company-22` | 1.00 | 5 | — | 正常通读 |
| `official-company-24` | 0.33 | 5 | — | 检查过度引用 |
| `official-welfare-02` | 0.33 | 5 | — | 检查过度引用 |
| `official-welfare-04` | 0.50 | 5 | — | 检查过度引用 |
| `official-welfare-06` | 1.00 | 5 | — | 正常通读 |
| `official-welfare-08` | 1.00 | 5 | — | 正常通读 |
| `official-welfare-10` | 1.00 | 5 | — | 正常通读 |
| `official-welfare-12` | 0.50 | 5 | — | 检查过度引用 |
| `official-welfare-14` | 0.33 | 5 | — | 检查过度引用 |
| `official-welfare-16` | 0.20 | 5 | cz-company-change-registration | 检查过度引用；检查跨文档引用 |

## Suggested review order

先看有标记的样本，再通读其余样本：

1. `official-company-02`
2. `official-company-06`
3. `official-company-08`
4. `official-company-12`
5. `official-company-16`
6. `official-company-18`
7. `official-company-20`
8. `official-company-24`
9. `official-welfare-02`
10. `official-welfare-04`
11. `official-welfare-12`
12. `official-welfare-14`
13. `official-welfare-16`

## Review checklist

1. Compare the answer with the question and gold evidence, not only the automatic judge.
2. Mark every cited source that does not support the sentence it is attached to.
3. Check whether any material condition, deadline, place or required document is missing.
4. Record unsupported claims the judge missed.
5. Put the final pass/fail decision only in the human review sheet.

## Full evidence

- `docs/experiments/20261124-official-answer-quality-test-review.md`
- `docs/experiments/20261124-official-answer-quality-test.json`

## Limitations

- Citation precision is a strict document+heading match and can flag harmless extra context.
- Completeness below 5 is a prioritization signal, not automatically a failure.
- This automated triage is not an independent human judgement.
