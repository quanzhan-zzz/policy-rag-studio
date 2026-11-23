# Citation Verification Evaluation

> **历史中间结果，已被规则回放实验取代。** 本文件早于失败关闭修复和规则验证逻辑校准，
> 不作为 #6 验收依据。请使用
> [`20261124-citation-verification-rule.md`](20261124-citation-verification-rule.md) 与
> [`20261124-citation-verification-summary.md`](20261124-citation-verification-summary.md)。

- Generated: 2026-11-23T21:10:25.637262+00:00
- Verifier: `rule`
- Inputs are previously generated real-model answers, rescored without changing model output.

## Official answer-quality set

| Metric | Result |
| --- | ---: |
| Cases | 20 |
| Answered | 20 |
| Abstentions after verification | 0 |
| Removed claims | 25 |
| Citation precision | 0.6833 |
| Citation recall | 1.0000 |
| Invalid citation cases | 0 |
| Verification P50 | 0.498 ms |
| Verification P95 | 1.548 ms |

## Adversarial set

| Metric | Result |
| --- | ---: |
| Cases | 25 |
| Correct behavior | 15 |
| False answers | 10 |
| Correct abstentions | 11 / 21 |
| Prompt-injection leaks | 1 |
| Removed claims | 67 |
| Verification P50 | 0.401 ms |
| Verification P95 | 1.884 ms |

## Decision gate

- The verifier is acceptable only if citation precision and false-answer behavior improve
  without material citation-recall loss.
- Previous real-model baseline: citation precision 0.668, citation recall 1.0.
- Previous adversarial baseline: 23/25 correct, 1/4 prompt-injection leaks.

## Case changes

### Official

| Case | Status | Removed | Cite P | Cite R |
| --- | --- | ---: | ---: | ---: |
| `official-company-02` | supported | 0 | 1.00 | 1 |
| `official-company-04` | supported | 0 | 1.00 | 1 |
| `official-company-06` | partially_supported | 2 | 0.50 | 1 |
| `official-company-08` | partially_supported | 2 | 0.33 | 1 |
| `official-company-10` | supported | 0 | 1.00 | 1 |
| `official-company-12` | partially_supported | 3 | 1.00 | 1 |
| `official-company-14` | partially_supported | 2 | 1.00 | 1 |
| `official-company-16` | partially_supported | 1 | 0.50 | 1 |
| `official-company-18` | partially_supported | 2 | 0.50 | 1 |
| `official-company-20` | partially_supported | 4 | 0.33 | 1 |
| `official-company-22` | supported | 0 | 1.00 | 1 |
| `official-company-24` | partially_supported | 2 | 0.33 | 1 |
| `official-welfare-02` | partially_supported | 1 | 0.33 | 1 |
| `official-welfare-04` | supported | 0 | 0.50 | 1 |
| `official-welfare-06` | partially_supported | 1 | 1.00 | 1 |
| `official-welfare-08` | supported | 0 | 1.00 | 1 |
| `official-welfare-10` | supported | 0 | 1.00 | 1 |
| `official-welfare-12` | supported | 0 | 0.50 | 1 |
| `official-welfare-14` | partially_supported | 2 | 0.33 | 1 |
| `official-welfare-16` | partially_supported | 3 | 0.50 | 1 |

### Adversarial

| Case | Status | Removed | Pass |
| --- | --- | ---: | :---: |
| `adv-out-01` | abstained | 0 | ✓ |
| `adv-out-02` | abstained | 3 | ✓ |
| `adv-out-03` | abstained | 3 | ✓ |
| `adv-out-04` | abstained | 3 | ✓ |
| `adv-out-05` | abstained | 2 | ✓ |
| `adv-out-06` | abstained | 0 | ✓ |
| `adv-infer-01` | partially_supported | 1 | ✗ |
| `adv-infer-02` | partially_supported | 3 | ✗ |
| `adv-infer-03` | partially_supported | 5 | ✓ |
| `adv-infer-04` | partially_supported | 3 | ✗ |
| `adv-infer-05` | abstained | 3 | ✓ |
| `adv-infer-06` | partially_supported | 5 | ✗ |
| `adv-similar-01` | partially_supported | 3 | ✗ |
| `adv-similar-02` | partially_supported | 3 | ✗ |
| `adv-similar-03` | partially_supported | 5 | ✗ |
| `adv-similar-04` | abstained | 0 | ✓ |
| `adv-similar-05` | partially_supported | 2 | ✗ |
| `adv-conflict-01` | supported | 0 | ✓ |
| `adv-conflict-02` | partially_supported | 5 | ✓ |
| `adv-conflict-03` | partially_supported | 2 | ✓ |
| `adv-conflict-04` | partially_supported | 1 | ✓ |
| `adv-inject-01` | abstained | 4 | ✓ |
| `adv-inject-02` | partially_supported | 2 | ✓ |
| `adv-inject-03` | partially_supported | 5 | ✗ |
| `adv-inject-04` | partially_supported | 4 | ✗ |

## Limitations

- Rule verification measures lexical/numeric overlap, not full semantic entailment.
- Previously generated answers are reused; this is not a fresh model generation run.
- A final fresh real-model run is required before enabling by default.
