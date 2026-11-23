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
          title="执行记录"
          description="选择一条 Trace 查看阶段耗时。"
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
        title="执行详情"
        description="按时间顺序检查召回、融合、重排与生成阶段。"
        aside={
          <Link className="button button-ghost" to="/retrieval">
            <ArrowLeft size={15} /> 返回对比
          </Link>
        }
      />

      <section className="trace-header-grid">
        <article className="panel trace-query-panel">
          <h3>{data.query}</h3>
          <div className="trace-meta-row">
            <span><GitBranch size={14} /> {data.strategy}</span>
            <span><Workflow size={14} /> {data.chunk_strategy}</span>
            <span><Clock3 size={14} /> {data.total_ms.toFixed(2)} ms</span>
          </div>
          <small className="trace-id">{data.id}</small>
        </article>
        <article className="panel trace-summary-panel">
          <strong>{data.stages.length}</strong>
          <p>记录阶段 · 从 tokenize 到 Context Pack</p>
        </article>
      </section>

      <article className="panel trace-timeline-panel">
        <div className="panel-heading">
          <div>
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

    </div>
  )
}
