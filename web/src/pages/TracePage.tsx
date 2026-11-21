import { ArrowLeft, Clock3, GitBranch, SearchCode, Workflow } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/StateBlock'
import { useTrace } from '../lib/queries'

export function TracePage() {
  const { traceId } = useParams()
  const trace = useTrace(traceId)
  const maxDuration = trace.data?.stages.reduce(
    (maximum, stage) => Math.max(maximum, stage.duration_ms),
    0.01,
  )

  if (!traceId) {
    return (
      <div className="page-stack">
        <PageHeader
          marker="FIELD NOTE / 06"
          title="Trace 检索执行链"
          description="从检索对比结果进入某条策略，才能看到查询解析、召回、RRF 融合和重排的完整阶段。"
        />
        <div className="panel trace-empty">
          <SearchCode size={30} />
          <h3>尚未选择 Trace</h3>
          <p>打开检索对比页面，运行一次实验，然后点击任意结果卡片中的 Trace。</p>
          <Link className="button button-primary" to="/retrieval">
            去检索对比
          </Link>
        </div>
      </div>
    )
  }

  if (trace.isLoading) return <LoadingState label="正在读取 Trace 执行链" />
  if (trace.isError) return <ErrorState message={trace.error.message} />

  const data = trace.data!
  return (
    <div className="page-stack">
      <PageHeader
        marker="FIELD NOTE / 06"
        title="每一次排名变化都可追溯"
        description="Trace 保存查询、策略、阶段数量、耗时和中间说明。它用于判断问题来自查询解析、召回、融合还是重排。"
        aside={
          <Link className="button button-ghost" to="/retrieval">
            <ArrowLeft size={15} /> 返回对比
          </Link>
        }
      />

      <section className="trace-header-grid">
        <article className="panel trace-query-panel">
          <span className="panel-index">A / QUERY SNAPSHOT</span>
          <h3>{data.query}</h3>
          <div className="trace-meta-row">
            <span><GitBranch size={14} /> {data.strategy}</span>
            <span><Workflow size={14} /> {data.chunk_strategy}</span>
            <span><Clock3 size={14} /> {data.total_ms.toFixed(2)} ms</span>
          </div>
          <small className="trace-id">{data.id}</small>
        </article>
        <article className="panel trace-summary-panel">
          <span className="panel-index">B / STAGE COUNT</span>
          <strong>{data.stages.length}</strong>
          <p>记录阶段 · 从 tokenize 到 Context Pack</p>
        </article>
      </section>

      <article className="panel trace-timeline-panel">
        <div className="panel-heading">
          <div>
            <span className="panel-index">C / EXECUTION TIMELINE</span>
            <h3>执行阶段与耗时</h3>
          </div>
          <span className="quiet-chip">created {new Date(data.created_at).toLocaleTimeString('zh-CN')}</span>
        </div>
        <div className="trace-timeline">
          {data.stages.map((stage, index) => (
            <div className="trace-stage" key={`${stage.key}-${index}`}>
              <div className="trace-stage-index">{String(index + 1).padStart(2, '0')}</div>
              <div className="trace-stage-copy">
                <div className="trace-stage-title">
                  <div>
                    <span>{stage.key}</span>
                    <strong>{stage.label}</strong>
                  </div>
                  <span className="mono-value">{stage.duration_ms.toFixed(2)} ms</span>
                </div>
                <div className="trace-stage-track">
                  <span
                    style={{
                      width: `${Math.max(3, (stage.duration_ms / (maxDuration || 1)) * 100)}%`,
                    }}
                  />
                </div>
                <div className="trace-stage-detail">
                  <p>{stage.detail}</p>
                  <span>
                    IN {stage.input_count ?? '—'} / OUT {stage.output_count ?? '—'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </article>

      <section className="trace-note-grid">
        <article className="panel">
          <span className="panel-index">D / INTERPRETATION</span>
          <h3>如何读这条 Trace</h3>
          <p>
            先比较 Dense 与 BM25 的候选差异，再观察 RRF 融合是否把正确条款拉到前面。若
            Rerank 后排名反向下降，应检查重排模型的训练域和输入长度。
          </p>
        </article>
        <article className="panel accent-panel">
          <span className="panel-index">E / NEXT EXPERIMENT</span>
          <h3>替换真实 Provider</h3>
          <p>
            当前 Dense 和 Rerank 是可复现的演示实现。接入 BGE-M3 与 BGE Reranker
            后，前端不需要改变，只需重新运行同一批评测集。
          </p>
        </article>
      </section>
    </div>
  )
}
