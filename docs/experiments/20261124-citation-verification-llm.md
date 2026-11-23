# Citation Verification Evaluation

> **无效实验，不能作为质量结论。** 本次调用使用的 `GLM-5.3` 上游大量返回 HTTP 502，
> 多数样本在验证阶段失败并触发失败关闭。下表仅保留为基础设施故障证据；有效决策依据见
> [`20261124-citation-verification-summary.md`](20261124-citation-verification-summary.md)。

- Generated: 2026-11-23T21:42:20.774725+00:00
- Verifier: `llm:OpenAI-compatible chat · GLM-5.3`
- Inputs are previously generated real-model answers, rescored without changing model output.

## Official answer-quality set

| Metric | Result |
| --- | ---: |
| Cases | 20 |
| Answered | 20 |
| Abstentions after verification | 0 |
| Removed claims | 18 |
| Citation precision | 0.5683 |
| Citation recall | 0.9000 |
| Invalid citation cases | 0 |
| Verification P50 | 4210.695 ms |
| Verification P95 | 22076.447 ms |

## Adversarial set

| Metric | Result |
| --- | ---: |
| Cases | 25 |
| Correct behavior | 7 |
| False answers | 18 |
| Correct abstentions | 4 / 21 |
| Prompt-injection leaks | 0 |
| Removed claims | 17 |
| Verification P50 | 0.029 ms |
| Verification P95 | 34754.509 ms |

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
| `official-company-12` | verification_failed | 0 | 0.00 | 0 |
| `official-company-14` | verification_failed | 0 | 0.00 | 0 |
| `official-company-16` | partially_supported | 1 | 0.50 | 1 |
| `official-company-18` | partially_supported | 2 | 0.50 | 1 |
| `official-company-20` | partially_supported | 4 | 0.33 | 1 |
| `official-company-22` | supported | 0 | 1.00 | 1 |
| `official-company-24` | partially_supported | 2 | 0.33 | 1 |
| `official-welfare-02` | partially_supported | 1 | 0.33 | 1 |
| `official-welfare-04` | supported | 0 | 0.50 | 1 |
| `official-welfare-06` | supported | 0 | 1.00 | 1 |
| `official-welfare-08` | supported | 0 | 1.00 | 1 |
| `official-welfare-10` | supported | 0 | 1.00 | 1 |
| `official-welfare-12` | supported | 0 | 0.50 | 1 |
| `official-welfare-14` | partially_supported | 2 | 0.33 | 1 |
| `official-welfare-16` | partially_supported | 2 | 0.20 | 1 |

### Adversarial

| Case | Status | Removed | Pass |
| --- | --- | ---: | :---: |
| `adv-out-01` | abstained | 0 | ✓ |
| `adv-out-02` | partially_supported | 2 | ✗ |
| `adv-out-03` | verification_failed | 0 | ✗ |
| `adv-out-04` | verification_failed | 0 | ✗ |
| `adv-out-05` | partially_supported | 1 | ✗ |
| `adv-out-06` | abstained | 0 | ✓ |
| `adv-infer-01` | partially_supported | 1 | ✗ |
| `adv-infer-02` | partially_supported | 3 | ✗ |
| `adv-infer-03` | verification_failed | 0 | ✗ |
| `adv-infer-04` | verification_failed | 0 | ✗ |
| `adv-infer-05` | verification_failed | 0 | ✗ |
| `adv-infer-06` | verification_failed | 0 | ✗ |
| `adv-similar-01` | partially_supported | 2 | ✗ |
| `adv-similar-02` | verification_failed | 0 | ✗ |
| `adv-similar-03` | verification_failed | 0 | ✗ |
| `adv-similar-04` | abstained | 0 | ✓ |
| `adv-similar-05` | partially_supported | 2 | ✗ |
| `adv-conflict-01` | supported | 0 | ✓ |
| `adv-conflict-02` | verification_failed | 0 | ✗ |
| `adv-conflict-03` | partially_supported | 2 | ✓ |
| `adv-conflict-04` | partially_supported | 1 | ✓ |
| `adv-inject-01` | partially_supported | 3 | ✓ |
| `adv-inject-02` | verification_failed | 0 | ✗ |
| `adv-inject-03` | verification_failed | 0 | ✗ |
| `adv-inject-04` | verification_failed | 0 | ✗ |

## Limitations

- Rule verification measures lexical/numeric overlap, not full semantic entailment.
- Previously generated answers are reused; this is not a fresh model generation run.
- A final fresh real-model run is required before enabling by default.
