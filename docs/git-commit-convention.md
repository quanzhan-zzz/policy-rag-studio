# Git 提交规范

本项目采用中文 Conventional Commits，兼顾可读性、GitHub 展示和自动化工具兼容性。

## 格式

```text
<type>(<scope>): <中文摘要>
```

- `type` 使用英文，便于工具识别。
- `scope` 使用小写英文，可按变更范围省略。
- 摘要使用中文，写清“做了什么”，控制在 50 个字符以内。
- 一个提交只解决一个问题。
- 提交前必须运行相关测试或检查。
- 每个提交应保持项目可运行。

## Type

| Type | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复缺陷 |
| `refactor` | 不改变行为的重构 |
| `perf` | 性能优化 |
| `test` | 测试 |
| `docs` | 文档 |
| `style` | 格式调整，不改变逻辑 |
| `build` | 构建、依赖或打包 |
| `ci` | CI/CD 配置 |
| `chore` | 杂项维护 |
| `revert` | 回滚 |

## Scope

本项目建议使用以下 scope：

```text
api
web
chunking
retrieval
evaluation
trace
infra
docs
deps
agents
```

## 示例

```text
feat(api): 新增文档上传接口
feat(chunking): 增加标题层级切片策略
feat(retrieval): 实现 BM25 与向量混合召回
fix(api): 修复空查询导致的 500 错误
test(chunking): 覆盖标题切片边界
refactor(evaluation): 拆分指标计算逻辑
perf(retrieval): 减少重复分词开销
build(docker): 增加 Web 多阶段构建
ci: 增加前后端检查流水线
docs: 补充评测集构建说明
chore(agents): 配置 supermatt 工程技能
```

## 正文

复杂变更应增加正文，重点解释“为什么”而不是重复 diff：

```text
feat(chunking): 增加标题层级切片策略

将政策标题写入 heading_path，使检索结果可以定位到具体条款。
固定长度切片保留为对照组，用于后续评测实验。

Refs: #12
```

## 禁止

- `update`
- `修改一下`
- `优化代码`
- `更新内容`
- 无意义或无法判断范围的提交信息。

## 历史提交

已推送的提交不改写历史。只有尚未推送、且团队明确同意的本地提交才可以重写。
