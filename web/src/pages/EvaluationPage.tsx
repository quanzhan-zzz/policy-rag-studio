import { AlertCircle, FlaskConical, Gauge, Scale } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { MetricCard } from '../components/MetricCard'
import { PageHeader } from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/StateBlock'
import { useEvaluation } from '../lib/queries'

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export function EvaluationPage() {
  const evaluation = useEvaluation()

  if (evaluation.isLoading) return <LoadingState label="正在计算评测指标" />
  if (evaluation.isError) return <ErrorState message={evaluation.error.message} />

  const data = evaluation.data!
  const chartData = data.rows.map((row) => ({
    name: row.label,
    recall: Number((row.recall_at_5 * 100).toFixed(1)),
    mrr: Number((row.mrr * 100).toFixed(1)),
    ndcg: Number((row.ndcg_at_5 * 100).toFixed(1)),
  }))
  const best = data.rows.reduce((current, row) =>
    row.recall_at_5 > current.recall_at_5 ? row : current,
  )

  return (
    <div className="page-stack">
      <PageHeader
        marker="FIELD NOTE / 05"
        title="评测报告，不是感觉报告"
        description="同一批政策问题、同一批相关条款，对比检索策略的 Recall@5、MRR、nDCG 和 P95 延迟。指标由后端脚本实时计算。"
        aside={
          <div className="date-block">
            <span>DATASET</span>
            <strong>{data.case_count} cases</strong>
            <small>
              {data.dataset_name} / {data.split ?? 'all'}
            </small>
            <small>reranker: {data.reranker_provider ?? 'not recorded'}</small>
          </div>
        }
      />

      <section className="metric-grid evaluation-metrics">
        <MetricCard
          detail={best.label}
          icon={<FlaskConical size={17} />}
          label="Best recall@5"
          tone="blue"
          value={percent(best.recall_at_5)}
        />
        <MetricCard
          detail="平均 reciprocal rank"
          icon={<Scale size={17} />}
          label="Best MRR"
          tone="green"
          value={best.mrr.toFixed(3)}
        />
        <MetricCard
          detail="前五名排序质量"
          icon={<Gauge size={17} />}
          label="Best nDCG@5"
          tone="amber"
          value={best.ndcg_at_5.toFixed(3)}
        />
        <MetricCard
          detail="最优策略 P95"
          icon={<AlertCircle size={17} />}
          label="Latency"
          value={`${best.p95_ms.toFixed(1)} ms`}
        />
      </section>

      <section className="evaluation-layout">
        <article className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-index">A / QUALITY COMPARISON</span>
              <h3>质量指标横向对比</h3>
            </div>
            <span className="quiet-chip">higher is better</span>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={chartData} margin={{ top: 18, right: 12, left: -18, bottom: 4 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="2 4" vertical={false} />
                <XAxis
                  axisLine={false}
                  dataKey="name"
                  tick={{ fill: 'var(--muted)', fontSize: 11 }}
                  tickLine={false}
                />
                <YAxis
                  axisLine={false}
                  domain={[0, 100]}
                  tick={{ fill: 'var(--muted)', fontSize: 10 }}
                  tickLine={false}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    border: '1px solid var(--line-strong)',
                    borderRadius: 2,
                    background: 'var(--paper)',
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="recall" fill="var(--signal)" name="Recall@5" radius={[2, 2, 0, 0]} />
                <Bar dataKey="mrr" fill="var(--teal)" name="MRR" radius={[2, 2, 0, 0]} />
                <Bar dataKey="ndcg" fill="var(--amber)" name="nDCG@5" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-legend">
            <span><i className="legend-blue" /> Recall@5</span>
            <span><i className="legend-teal" /> MRR</span>
            <span><i className="legend-amber" /> nDCG@5</span>
          </div>
        </article>

        <article className="panel failure-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-index">B / FAILURE NOTES</span>
              <h3>失败样本分类</h3>
            </div>
          </div>
          {data.failures.length ? (
            <div className="failure-list">
              {data.failures.map((failure, index) => (
                <div key={failure.type}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <p>{failure.type}</p>
                  <strong>{failure.count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="success-note">
              <CheckMark />
              <div>
                <strong>当前演示集未发现 Top-5 漏召回</strong>
                <p>这不代表生产效果。接入真实政策和更多口语化问题后再建立置信结论。</p>
              </div>
            </div>
          )}
        </article>
      </section>

      <article className="panel metric-ledger">
        <div className="panel-heading">
          <div>
            <span className="panel-index">C / METRIC LEDGER</span>
            <h3>完整指标账本</h3>
          </div>
          <span className="quiet-chip">generated {new Date(data.generated_at).toLocaleTimeString('zh-CN')}</span>
        </div>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>策略</th>
                <th>Recall@5</th>
                <th>MRR</th>
                <th>nDCG@5</th>
                <th>P95 延迟</th>
                <th>判断</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.strategy}>
                  <td>
                    <strong>{row.label}</strong>
                    <span className="table-subline">{row.strategy}</span>
                  </td>
                  <td className="mono-cell">{percent(row.recall_at_5)}</td>
                  <td className="mono-cell">{row.mrr.toFixed(4)}</td>
                  <td className="mono-cell">{row.ndcg_at_5.toFixed(4)}</td>
                  <td className="mono-cell">{row.p95_ms.toFixed(2)} ms</td>
                  <td>
                    <span className={`status-pill ${row.strategy === best.strategy ? 'is-best' : 'is-indexed'}`}>
                      <span />
                      {row.strategy === best.strategy ? '首选' : '对照'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </div>
  )
}

function CheckMark() {
  return (
    <span className="check-mark" aria-hidden="true">
      ✓
    </span>
  )
}
