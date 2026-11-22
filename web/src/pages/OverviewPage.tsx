import { ArrowUpRight, Database, FileStack, FlaskConical, TimerReset } from 'lucide-react'
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
        marker="FIELD NOTE / 01"
        title="把检索质量变成可见证据"
        description="一个面向政策知识的切片、混合检索与评测工作台。页面上呈现的不是聊天结果，而是每个检索决策前后的证据。"
        aside={
          <div className="date-block">
            <span>OBSERVATION DATE</span>
            <strong>{observationDate}</strong>
            <small>Changzhou · Local demo</small>
          </div>
        }
      />

      <section className="metric-grid">
        <MetricCard
          detail="公开政策与演示文档"
          icon={<FileStack size={17} />}
          label="Documents"
          tone="blue"
          value={data.document_count}
        />
        <MetricCard
          detail="三种切片策略"
          icon={<Database size={17} />}
          label="Indexed chunks"
          tone="green"
          value={data.chunk_count}
        />
        <MetricCard
          detail={`${evaluation?.case_count ?? 0} 条政策问答`}
          icon={<FlaskConical size={17} />}
          label="Evaluation set"
          value={data.evaluation_case_count}
        />
        <MetricCard
          detail={`最佳召回 ${formatPercent(bestRun?.recall_at_5 ?? 0)}`}
          icon={<TimerReset size={17} />}
          label="Retrieval runs"
          tone="amber"
          value={data.retrieval_runs}
        />
      </section>

      <section className="overview-grid">
        <article className="panel panel-wide">
          <div className="panel-heading">
            <div>
              <span className="panel-index">A / RETRIEVAL HEALTH</span>
              <h3>策略谱系</h3>
            </div>
            <Link className="text-link" to="/evaluation">
              打开评测 <ArrowUpRight size={14} />
            </Link>
          </div>
          <div className="strategy-list">
            {evaluation?.rows.map((row, index) => (
              <div className="strategy-row" key={row.strategy}>
                <span className="strategy-number">{String(index + 1).padStart(2, '0')}</span>
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
              <span className="panel-index">B / SYSTEM MATRIX</span>
              <h3>运行环境</h3>
            </div>
          </div>
          <div className="matrix-list">
            <div>
              <span>API</span>
              <strong className="ok-text">ONLINE</strong>
            </div>
            <div>
              <span>Vector backend</span>
              <strong>PGVECTOR / READY</strong>
            </div>
            <div>
              <span>Embedding</span>
              <strong>{data.model_provider.toLowerCase().includes('hash') ? 'HASH / DEMO' : 'QWEN / API'}</strong>
            </div>
            <div>
              <span>LLM</span>
              <strong>{data.llm_provider.toLowerCase().includes('glm') ? 'GLM / API' : 'API / READY'}</strong>
            </div>
            <div>
              <span>Chunk profiles</span>
              <strong>03</strong>
            </div>
          </div>
          <p className="panel-footnote">{data.model_provider}</p>
          <p className="panel-footnote">{data.llm_provider}</p>
        </article>
      </section>

      <section className="overview-grid overview-bottom">
        <article className="panel panel-wide">
          <div className="panel-heading">
            <div>
              <span className="panel-index">C / RECENT OBSERVATIONS</span>
              <h3>当前实验结论</h3>
            </div>
            <span className="quiet-chip">sample data</span>
          </div>
          <div className="observation-grid">
            <div className="observation">
              <span className="observation-tag">01 / CHUNKING</span>
              <h4>标题切片保留条款边界</h4>
              <p>政策标题会进入 heading path，引用展示和人工复核更容易定位。</p>
            </div>
            <div className="observation">
              <span className="observation-tag">02 / HYBRID</span>
              <h4>关键词补足精确条款</h4>
              <p>BM25 与向量召回经 RRF 合并，政策编号和专有名词更难漏掉。</p>
            </div>
            <div className="observation">
              <span className="observation-tag">03 / RERANK</span>
              <h4>只重排高价值候选</h4>
              <p>Top 30 进入重排，保留质量收益，同时控制演示环境的额外延迟。</p>
            </div>
          </div>
        </article>

        <article className="panel note-panel">
          <span className="panel-index">D / CAVEAT</span>
          <h3>这是可复现骨架</h3>
          <p>
            Dense 与 Reranker 当前使用确定性演示实现。接口已隔离，下一步接入 BGE-M3 和
            BGE Reranker 时不需要改动前端数据契约。
          </p>
          <Link className="button button-ghost" to="/chunk-lab">
            进入 Chunk Lab
          </Link>
        </article>
      </section>
    </div>
  )
}
