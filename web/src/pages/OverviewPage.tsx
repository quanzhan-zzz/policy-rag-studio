import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ErrorState, LoadingState } from '../components/StateBlock'
import { MetricCard } from '../components/MetricCard'
import { PageHeader } from '../components/PageHeader'
import { useOverview } from '../lib/queries'

const observationDate = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date())

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export function OverviewPage() {
  const overview = useOverview()
  if (overview.isLoading) return <LoadingState />
  if (overview.isError) return <ErrorState message={overview.error.message} />

  const data = overview.data!
  const evaluation = data.last_evaluation
  const bestRun = evaluation?.rows.reduce((best, row) =>
    row.recall_at_5 > best.recall_at_5 ? row : best,
  )

  return (
    <div className="page-stack">
      <PageHeader
        title="工作台概览"
        description="知识库规模、检索质量与最近实验状态。"
        aside={
          <div className="date-block">
            <span>检查日期</span>
            <strong>{observationDate}</strong>
            <small>本地政策演示库</small>
          </div>
        }
      />

      <section className="metric-grid">
        <MetricCard
          detail="公开政策与演示文档"
          label="文档数"
          value={data.document_count}
        />
        <MetricCard
          detail="三种切片策略"
          label="已索引切片"
          value={data.chunk_count}
        />
        <MetricCard
          detail={`${evaluation?.case_count ?? 0} 条政策问答`}
          label="评测样本"
          value={data.evaluation_case_count}
        />
        <MetricCard
          detail={`最佳召回 ${formatPercent(bestRun?.recall_at_5 ?? 0)}`}
          label="检索运行"
          value={data.retrieval_runs}
        />
      </section>

      <section className="overview-grid">
        <article className="panel panel-wide">
          <div className="panel-heading">
            <div>
              <h3>策略谱系</h3>
            </div>
            <Link className="text-link" to="/evaluation">
              打开评测 <ArrowUpRight size={13} />
            </Link>
          </div>
          <div className="strategy-list">
            {evaluation?.rows.map((row) => (
              <div className="strategy-row" key={row.strategy}>
                <div className="strategy-main">
                  <div className="strategy-title">
                    <strong>{row.label}</strong>
                    <span>{formatPercent(row.recall_at_5)} recall@5</span>
                  </div>
                  <div className="score-track">
                    <span style={{ width: `${Math.max(4, row.recall_at_5 * 100)}%` }} />
                  </div>
                </div>
                <div className="strategy-value">
                  <strong>{row.mrr.toFixed(3)}</strong>
                  <span>MRR</span>
                </div>
                <div className="strategy-value">
                  <strong>{row.p95_ms.toFixed(1)}</strong>
                  <span>ms p95</span>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <h3>运行环境</h3>
            </div>
          </div>
          <div className="matrix-list">
            <div><span>API</span><strong className="ok-text">在线</strong></div>
            <div><span>向量库</span><strong>PGVector / 就绪</strong></div>
            <div><span>向量模型</span><strong>{data.model_provider.toLowerCase().includes('hash') ? 'Hash / 演示' : 'Qwen / API'}</strong></div>
            <div><span>生成模型</span><strong>{data.llm_provider.toLowerCase().includes('glm') ? 'GLM / API' : 'API / 就绪'}</strong></div>
            <div><span>切片策略</span><strong>03</strong></div>
          </div>
          <p className="panel-footnote">{data.model_provider} · {data.llm_provider}</p>
        </article>
      </section>

      <article className="panel note-panel note-strip">
        <div>
          <h3>实现说明</h3>
          <p>Dense 与 Reranker 为确定性演示实现；接入 BGE-M3 与 BGE Reranker 时，前端数据契约不变。</p>
        </div>
        <Link className="button button-ghost" to="/chunk-lab">进入切片实验</Link>
      </article>
    </div>
  )
}
