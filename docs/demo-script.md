# PolicyRAG Studio · 3 分钟演示脚本

## 0:00–0:25 问题

普通 RAG Demo 只展示最终答案。这个项目用于比较切分、召回、融合、重排和引用是否可靠。

## 0:25–0:55 文档与异步索引

1. 打开“文档管理”
2. 上传 Markdown/PDF
3. 展示 `queued → parsing → chunking → embedding → ready`
4. 指出索引由 Celery Worker 完成，不是 HTTP 请求内同步执行

## 0:55–1:30 Chunk 与检索

1. 打开 Chunk Lab，切换固定长度、标题层级、递归切片
2. 打开检索对比，运行一个政策问题
3. 比较 Dense、BM25、Hybrid 和 Rerank 的候选及排名变化

## 1:30–2:20 流式回答与证据

1. 生成带引用回答
2. 指出答案逐字输出、首字延迟、总耗时、Token usage
3. 展开 SOURCE REGISTER，核对引用原文
4. 打开 Trace，展示检索、重排、生成阶段

## 2:20–2:50 评测与实验

1. 打开评测看板，说明 152 条合成政策集，开发集 114、测试集 38
2. 展示 BGE 实验：
   - Pure RRF MRR 0.6412
   - BGE Reranker MRR 0.7833
   - Rerank P95 109.3 ms

## 2:50–3:00 工程化

指出 PostgreSQL/pgvector、Alembic、Celery Beat stale-task 恢复、请求 ID 日志、GitHub Actions 和 Playwright。
