# 查询规划评测总结

- 日期：2026-11-24（Asia/Shanghai）
- 数据库：独立 PostgreSQL `policyrag_official_eval`
- 开发集：`policy-official-v1 / dev` + `policy-multicondition-v1 / dev`
- 测试集：`policy-official-v1 / test` + `policy-multicondition-v1 / test`
- Embedding：`qwen3.7-text-embedding-flash`
- Reranker：`BAAI/bge-reranker-base`
- Planner / Answer / Judge：`glm-5.3-flash`

## 模式

- `none`：原始查询进入生产 Hybrid + BGE 链路。
- `rewrite`：LLM 生成一个规范检索查询，与原始查询共同参与 RRF。
- `decompose`：LLM 生成宽查询和有限子查询，所有查询分别检索后做 RRF。
- LLM 超时、格式错误或没有有效子查询时回退原始查询。

## 开发集迭代

第一次 dev 实验发现纯 rewrite 会损失 Recall，因此改为始终保留原始查询，再进行融合。第二次 dev 实验后：

- rewrite 恢复 Recall@5 到 `1.0000`
- rewrite 的多条件章节覆盖从 `0.8182` 提升到 `0.9091`
- decompose 没有稳定超过基线
- 所有规划模式都增加约 4–5 秒 P95 规划延迟

随后冻结 planner prompt、超时、子查询上限和融合规则，只运行一次 test。

## 测试集检索结果

| Mode | Recall@5 | MRR | nDCG@5 | Planner P95 | End-to-end P95 | Avg planner tokens | Avg queries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 1.0000 | 0.8417 | 0.8812 | 0 ms | 964.4 ms | 0 | 1.00 |
| rewrite | 1.0000 | **0.8458** | **0.8846** | 4556.0 ms | 6303.0 ms | 275.5 | 2.00 |
| decompose | 1.0000 | 0.8250 | 0.8693 | 4444.2 ms | 9398.4 ms | 277.7 | 3.85 |

多条件 test 覆盖：

| Mode | Section coverage | Full coverage |
| --- | ---: | ---: |
| none | 0.8182 | 0.6667 |
| rewrite | 0.8182 | 0.6667 |
| decompose | 0.7273 | 0.5000 |

dev 上 rewrite 的多条件覆盖提升没有在 test 复现，因此不能把该收益视为稳定结论。

## 答案质量

| Mode | Completeness (1-5) | Citation precision | Judge pass | Avg answer latency | Avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| none | **4.85** | 66.8% | 100% | 6564.2 ms | 1282 |
| rewrite | 4.60 | 68.3% | 100% | 12489.5 ms | 1281 |
| decompose | 4.80 | 65.8% | 100% | 12170.6 ms | 1218 |

答案完整性没有提升，rewrite 和 decompose 都把平均回答耗时推到约 12 秒。LLM 裁判仍为同模型自评，不能作为独立质量结论。

## 决策

**默认继续使用 `QUERY_PLANNING_MODE=none`。**

- `rewrite` 保留为可配置实验能力：test MRR/nDCG 有极小提升，但延迟成本远大于收益。
- `decompose` 保留为可复现实验路径，但当前证据不支持上线。
- 超时/解析失败会回退原始查询，不允许把规划失败变成检索失败。
- 如果未来接入更快的规划模型或真实多跳政策问题，需要重新用独立 dev/test 评测。

## 报告

- [dev 调参](20261124-query-planning-dev.md)
- [test 检索与多条件覆盖](20261124-query-planning-test.md)
- [rewrite 回答质量](20261124-query-planning-rewrite-answer-quality.md)
- [decompose 回答质量](20261124-query-planning-decompose-answer-quality.md)

## 局限

- 多条件集只有 12 条，test 只有 6 条。
- Planner 与回答模型相同；规划结果可能存在同模型偏差。
- 延迟包含外部 LLM 规划、Embedding 和 BGE，绝对数值受网络影响。
- 当前没有真实用户多轮查询和跨文档跳转流量。
