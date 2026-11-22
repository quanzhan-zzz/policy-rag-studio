# Development Roadmap

> 状态基线：`v0.1` 可运行演示版
> 更新时间：2026-11-22
> 当前目标：把 PolicyRAG Studio 从“可演示原型”推进到“可部署、可评测、可解释”的求职项目。

## 1. 当前已完成

- 文档上传、三种 Chunk 策略和 Chunk 编辑
- Dense、BM25、Hybrid RRF、启发式 Rerank 检索对比
- 固定评测集上的 Recall@5、MRR、nDCG@5 与 P95 延迟
- Qwen Embedding 与 GLM 带引用回答
- 前端回答面板、原文引用和 Trace 跳转
- Docker Compose、单元测试和前端生产构建

当前缺口不是“再做一个页面”，而是让核心链路具备持久化、可观测和可量化的生产能力。

## 2. 推进原则

1. **一次只推进一个里程碑。** 当前里程碑未达到验收标准，不并行开启下一条主链路。
2. **接口先于实现。** 存储、检索、重排、生成均通过小型接口隔离；测试依赖接口，不依赖具体基础设施。
3. **至少两个适配器才保留 Seam。** 例如 Repository 同时保留内存实现和 PostgreSQL 实现；只有一种实现时不额外抽象。
4. **每个里程碑保持可运行。** 合并前必须通过后端检查、前端检查和对应的数据验证。
5. **结论必须可复现。** 评测结果、配置、原始数据和失败案例一起提交，不使用口头指标。
6. **暂缓非核心功能。** 多 Agent、租户权限、Kubernetes 和自研向量库不进入本轮主线。

## 3. 里程碑总览

| 里程碑 | 结果 | 依赖 | 状态 |
| --- | --- | --- | --- |
| M0 持久化 | 重启不丢数据，pgvector 成为真实检索后端 | 当前 `InMemoryStore` 契约 | **已完成** |
| M1 异步索引 | 上传与索引解耦，状态、进度、重试可见 | M0 | **已完成** |
| M2 重排与评测 | 真实 Reranker 与可信实验报告 | M0、M1 | **已完成** |
| M3 回答可靠性 | 流式回答、引用校验、异常降级 | M0、M2 | **已完成** |
| M4 交付与发布 | CI、E2E、监控、演示材料与 Release | M0–M3 | **已完成** |

```text
M0 持久化
  ├── M1 异步索引
  └── M2 重排与评测
          └── M3 回答可靠性
                  └── M4 交付与发布
```

M1 与 M2 有部分工作可并行，但 M1 先完成，避免评测建立在不稳定的数据生命周期上。

## 4. M0：持久化与 pgvector

### 目标

将文档、Chunk、向量、Trace 和评测结果从进程内存迁移到 PostgreSQL，使服务重启后数据仍然存在，并让 Dense 检索真正使用 pgvector。

### 交付

- 定义 `DocumentRepository`、`ChunkRepository`、`TraceRepository` 等小型接口
- 保留 `InMemory*Repository` 用于单元测试
- 实现 `Postgres*Repository`
- 接入 SQLAlchemy 2 async session 与 Alembic
- 建立文档、文档版本、Chunk、向量、Trace、评测运行等数据表
- 使用 pgvector + HNSW 执行 Dense 检索
- 通过 Seed 命令写入三份演示政策
- 为迁移、Repository 契约和 pgvector 查询增加测试

### 接口约束

- 调用方只依赖 Repository 接口，不直接创建数据库 Session
- Chunk 身份包含文档版本和切片策略，重建索引不产生重复记录
- 写入文档、Chunk 和向量时保持事务一致性
- 检索结果继续返回现有 `RetrievedChunk` 契约，前端无需感知存储变化

### 当前进度

- [x] 定义 `Store` 接口并保留 `InMemoryStore` 测试适配器
- [x] 实现文档、Chunk 和 Trace 的 PostgreSQL 适配器
- [x] Docker 重启后文档、Chunk、Trace 和评测结果仍然存在
- [x] 同一 Repository 契约测试同时通过内存实现和 PostgreSQL 实现
- [x] Dense 检索迁移到 pgvector，并建立 HNSW 索引
- [x] 接入 Alembic 并从空库完成迁移
- [x] 持久化评测结果
- [x] PostgreSQL 全链路回归、重启验证与前端冒烟测试

## 5. M1：异步索引流水线

### 目标

把上传、解析、切片、Embedding 和索引从同步请求中拆出，使大文档处理可观察、可重试、可恢复。

### 交付

- Redis + Celery Worker
- 文档任务状态：`queued → parsing → chunking → embedding → ready | failed`
- 进度、错误分类、有限次数重试和幂等键
- Embedding 批量提交与重复文本缓存
- 文档重新索引、任务取消和失败重试接口
- 前端显示真实任务进度与失败原因

### 接口约束

- 上传接口只创建文档和任务，不在 HTTP 请求内完成索引
- 任务重复投递不能产生重复 Chunk 或重复向量
- Worker 崩溃后任务可从最后稳定状态恢复
- 单个文档失败不影响其他文档

### 验收

- [x] 上传后立即返回文档 ID 和任务 ID
- [x] 页面可看到 queued、parsing、chunking、embedding、ready / failed
- [x] 重复触发重建索引保持幂等
- [x] 解析失败可观察错误，失败任务可重试并恢复
- [x] API 在 Worker 停止时仍能正常响应，Worker 恢复后处理积压任务
- [x] Worker 被强制终止后，stale-task 扫描器可重新投递并完成任务
- [x] queued / processing 任务可取消

## 6. M2：真实重排与可信评测

### 目标

用真实 Reranker 替代启发式规则，并通过固定数据集证明质量收益与延迟代价。

### 交付

- `RerankerProvider`：`none`、BGE Reranker、OpenAI 兼容接口
- Hybrid Top-N 重排，记录重排前后排名和增量延迟
- 至少 150 道带相关 Chunk 标注的政策问题
- 开发集与测试集分离
- 四种检索策略的统一评测
- 失败分类和 Markdown 实验报告
- 复用 `docs/experiments/00-template.md` 记录每次实验

### 接口约束

- Reranker 只处理候选集，不改变召回接口
- 模型不可用时降级到 `none`，并在结果中明确标识
- 评测输入、配置和原始输出必须可复现
- 指标没有提升时保留真实结论，不针对测试集调参

### 当前进度

- [x] 定义 `RerankerProvider` 并实现 none、heuristic、LLM、BGE 适配器
- [x] Hybrid Top-30 重排、rank delta、延迟和降级记录
- [x] 增加可复现 Reranker 实验脚本
- [x] 四种检索策略在同一数据集上完成对比
- [x] 生成 Recall@5、MRR、nDCG@5 和 P95 的实验报告
- [x] 评测集扩充到 152 条并区分开发集 114 / 测试集 38
- [x] 启发式 Reranker 对比纯 RRF 的合成测试集结论
- [x] 获得零降级的真实 BGE Reranker 实验
- [x] 记录 API 货币成本为 0，并测量本地 Reranker 增量延迟
- [x] 至少分析 5 个 Top-5 漏召回或非 Rank-1 案例

当前最终报告：`docs/experiments/20261122-bge-reranker-synthetic-test.md`。38 条测试集上，BGE Reranker 将 MRR 从纯 RRF 的 `0.6412` 提升到 `0.7833`，Recall@5 从 `0.9474` 提升到 `1.0000`，Rerank P95 为 `109.3 ms`。LLM 限流实验保留在 `docs/experiments/20261122-reranker-llm-rate-limited.md`，明确标记无效。

## 7. M3：回答可靠性

### 目标

让回答过程可观察、引用可验证、模型故障可降级。

### 交付

- `POST /api/v1/answer/stream` SSE 接口
- 前端展示检索、生成、完成三个阶段
- 引用编号与 Context Pack 的自动校验
- 无效引用标记和证据不足降级
- 超时、限流、空响应和非法模型输出的明确错误
- Token、首字延迟、总延迟和估算成本记录

### 接口约束

- 流式接口与普通回答接口共享同一 Context Pack 构造逻辑
- 回答中的每个引用编号必须对应真实 Chunk
- 模型故障不能伪装成正常空回答

### 当前进度

- [x] `POST /api/v1/answer/stream` SSE 接口
- [x] 前端增量渲染回答
- [x] 普通回答与流式回答共享同一 Context Pack
- [x] 首字延迟与总耗时记录
- [x] 无效引用编号检测并返回
- [x] 模型流式错误转换为 SSE error 事件
- [x] 记录输入 / 输出 Token
- [x] Trace 增加生成阶段与 Token 信息
- [x] 断连时停止消费并取消上游流式生成
- [x] 无引用回答追加证据提示并标记 `uncited`
- [x] 无效引用回答追加证据提示并标记 `invalid_citations`

## 8. M4：交付与发布

### 目标

让新机器可以复现、团队成员可以维护、面试官可以快速理解。

### 交付

- GitHub Actions：Ruff、pytest、Lint、Vitest、Build
- Playwright：上传、切片、检索、回答、Trace
- Docker 健康检查与启动脚本
- 结构化日志、请求 ID 和关键接口耗时
- 架构图、数据模型图、检索流程图和评测报告
- 3 分钟演示脚本与固定演示数据
- `v0.2.0` Release

### 验收

- [x] 新机器按 README 可完成启动和演示
- [x] CI 配置覆盖后端、前端、PostgreSQL 契约和 E2E
- [x] Playwright 覆盖上传、Chunk Lab、检索、流式回答、评测与 Trace
- [x] 演示流程包含真实持久化、检索、引用和评测
- [x] README、架构文档、演示脚本和实验结果保持一致
- [x] 推送后 GitHub Actions 首次全绿
- [x] 创建 `v0.2.0` GitHub Release

## 9. 当前迭代边界

M3 已完成，下一步进入 M4。以下内容不进入 M4 主分支：

- 多 Agent 协作
- 多租户和复杂 RBAC
- Kubernetes
- 自研向量数据库
- 新的大面积前端页面
- Dify 或其他框架适配层

## 10. 下一次开发入口

从 M4 的可复现交付开始：

```text
GitHub Actions 覆盖后端 / 前端 / PostgreSQL 契约
→ Playwright 覆盖上传、检索、流式回答、评测和 Trace
→ 增加结构化日志和请求 ID
→ 完善 Docker 健康检查与一键启动
→ 更新架构图、演示脚本和截图
→ 创建 v0.2.0 Release
```
