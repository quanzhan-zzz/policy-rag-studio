# 引用支持校验与证据不足拒答总结

- 日期：2026-11-24（Asia/Shanghai）
- Issue：GitHub #6
- 实现状态：已完成，默认关闭
- 默认配置：`CITATION_VERIFIER_PROVIDER=none`
- 验证器：`none / rule / llm`

## 问题

原有 citation guard 只检查引用编号是否存在于 Context Pack。真实测试中引用召回率为 `100%`，
但引用精确率只有 `66.8%`，说明“编号合法”不等于“原文支持结论”。对抗测试还观察到模型会把
恶意文档中的伪造密码写进回答，并把相似事项的规则套用到目标事项上。

## 实现

- `CitationVerifier` 接口隔离 `none`、规则和 LLM 三种实现。
- 规则验证按结论检查数字、日期、地点、主体、材料名称、流程步骤、否定和全称条件。
- 每条结论记录 `supported`、引用编号、支持引用编号、失败原因和失败类型。
- 无法被引用原文支持的结论会被删除；所有结论都被删除时输出明确的“无法确认”。
- 超时、调用异常或输出解析失败时失败关闭，不把未校验结果标为 supported。
- 同步回答、SSE 流式回答、回答 API 响应和 Trace 使用同一验证结果。
- Trace 新增 `verification` 阶段，记录验证器、状态、结论数、移除数、Token 和降级原因。
- 指令型证据被视为不可信，不能支持回答。

## 真实数据回放

在既有真实 GLM 回答上只重放验证器，其他输入保持不变：

| 指标 | 基线 | 规则验证 |
| --- | ---: | ---: |
| 官方引用精确率 | 66.8% | **68.33%** |
| 官方引用召回率 | 100% | **100%** |
| 官方无效引用 | 0% | **0%** |
| 对抗正确行为 | 23 / 25 | **24 / 25** |
| 对抗 False answers | 2 / 25 | **1 / 25** |
| 应拒答正确率 | 19 / 21 | **20 / 21** |
| Prompt-injection 泄露 | 1 / 4 | **0 / 4** |

规则验证回放 P95 约 `1.5 ms`（官方集）和 `1.9 ms`（对抗集），无模型 Token 成本。

回放仍保留一个失败案例 `adv-similar-01`：回答把公司变更材料套用到合伙企业问题，验证器
只删除了 3 条无引用或弱支持结论，仍保留了部分公司材料名称。该失败说明规则重叠不能代替
完整的语义蕴含判断。

原始证据：[规则回放报告](20261124-citation-verification-rule.md) ·
[规则回放 JSON](20261124-citation-verification-rule.json) ·
[对抗失败详情](20261124-adversarial-rule-verifier-evaluation.md)。

## 新生成的真实模型结果

在独立 PostgreSQL、真实 Qwen Embedding、真实 BGE Reranker 和真实 GLM 生成链路上重新生成回答：

| 指标 | 结果 |
| --- | ---: |
| 回答生成 | 20 / 20 |
| 引用精确率 | 73.3% |
| 引用召回率 | 100% |
| 无效引用率 | 0% |
| LLM 裁判通过率 | 95% |
| 平均完整度 | 4.25 / 5 |
| 平均回答耗时 | 5803 ms |
| 移除结论 | 40 |
| 验证失败 | 0 |

同配置对抗集：正确行为 `24 / 25`、False answers `1 / 25`、应拒答 `20 / 21`、
Prompt-injection 泄露 `0`、移除无支持结论 `78`。

报告：[新生成回答质量](20261124-citation-verification-answer-quality.md) ·
[新生成对抗评测](20261124-adversarial-rule-verifier-evaluation.md)。

## 决策

**不默认开启。** 规则验证提高了引用精确率、错误回答抑制和注入泄露防护，但新生成回答的
完整度从基线 `4.85` 降到 `4.25`，且仍有一个相似事项错误。对于政策问答，过度删减会破坏
办理条件和材料清单，不能只依据引用精确率上线。

因此：

- 默认 `CITATION_VERIFIER_PROVIDER=none`，保留原有行为。
- API 可按请求启用 `citation_verifier_provider=rule`，用于高安全场景和演示。
- LLM 验证器保留实现和开关，但本次实验因上游 `502` 不稳定，不能给出有效质量结论。
- 后续需要独立的语义蕴含验证和人工复核，不应把当前规则验证描述为完整事实核查。

## 真实链路验收

当前容器使用真实 PostgreSQL、Redis、官方语料和配置模型完成：

- 同步 `POST /api/v1/answer` 返回 `verification_status=supported`、逐条 `verification_claims`
  和独立 Trace。
- SSE `POST /api/v1/answer/stream` 返回 `partially_supported`、`verified_claim_count=4`、
  `removed_claim_count=2`，Trace 记录相同结论。
- 默认 `none` 返回 `not_run`，不会伪造验证通过。
- PostgreSQL Repository 契约 `12 passed`。
- Playwright 真实浏览器路径 `6 passed`。

## 复现

```bash
# 回放既有真实回答，不重新调用回答模型
uv run python -m app.experiments.citation_verification_benchmark \
  --verifier rule \
  --output docs/experiments/20261124-citation-verification-rule.md

# 生成新的真实回答（需真实 PostgreSQL、Embedding 和 LLM）
DATABASE_URL='postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_official_eval' \
  STORE_BACKEND=postgres RERANKER_PROVIDER=bge \
  uv run python -m app.experiments.answer_quality \
  --dataset policy-official-v1 --split test --top-k 5 \
  --citation-verifier rule \
  --output docs/experiments/20261124-citation-verification-answer-quality.md
```

## 限制

- 规则验证衡量词汇、数字和条件重叠，不等于完整语义蕴含。
- 验证器可能删除结构标题、过渡句和跨引用合并句，影响可读性和完整度。
- LLM 验证依赖外部服务，本次实验受 `502` 和长尾延迟影响，结果无效。
- 20 条人工复核仍未完成，AI 不代填人工通过/不通过结论。
