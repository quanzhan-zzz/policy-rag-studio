import { ArrowRight, CornerDownRight, Play, Waypoints } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { AnswerPanel } from '../components/AnswerPanel'
import { PageHeader } from '../components/PageHeader'
import { ErrorState } from '../components/StateBlock'
import { useCompareRetrieval } from '../lib/queries'
import { useAnswerStream } from '../lib/useAnswerStream'
import type { ChunkStrategy, RetrievalStrategy } from '../types'

const allStrategies: { value: RetrievalStrategy; label: string; note: string }[] = [
  { value: 'dense', label: 'Dense', note: '哈希向量 / 演示' },
  { value: 'bm25', label: 'BM25', note: '精确词与条款' },
  { value: 'hybrid', label: 'Hybrid', note: 'RRF 融合' },
  { value: 'hybrid_rerank', label: 'Rerank', note: 'Top 30 重排' },
]

const chunkStrategies: { value: ChunkStrategy; label: string }[] = [
  { value: 'heading', label: '标题层级' },
  { value: 'recursive', label: '递归切片' },
  { value: 'fixed', label: '固定长度' },
]

const defaultQuery = '个体工商户登记需要准备哪些申请材料'

export function RetrievalPage() {
  const [query, setQuery] = useState(defaultQuery)
  const [topK, setTopK] = useState(5)
  const [chunkStrategy, setChunkStrategy] = useState<ChunkStrategy>('heading')
  const [strategies, setStrategies] = useState<RetrievalStrategy[]>(
    allStrategies.map((item) => item.value),
  )
  const comparison = useCompareRetrieval()
  const answer = useAnswerStream()
  const booted = useRef(false)

  const execute = () => {
    if (!query.trim() || strategies.length === 0) return
    comparison.mutate({
      query: query.trim(),
      strategies,
      chunk_strategy: chunkStrategy,
      top_k: topK,
    })
  }

  useEffect(() => {
    if (!booted.current) {
      booted.current = true
      comparison.mutate({
        query: defaultQuery,
        strategies: allStrategies.map((item) => item.value),
        chunk_strategy: 'heading',
        top_k: 5,
      })
    }
    // The initial comparison is intentionally run once when the workbench opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const generateAnswer = () => {
    if (!query.trim()) return
    void answer.start({
      query: query.trim(),
      chunk_strategy: chunkStrategy,
      top_k: topK,
      temperature: 0.1,
    })
  }

  const toggleStrategy = (strategy: RetrievalStrategy) => {
    setStrategies((current) =>
      current.includes(strategy)
        ? current.filter((item) => item !== strategy)
        : [...current, strategy],
    )
  }

  const runs = comparison.data?.runs ?? []
  const sharedChunkIds =
    runs.length > 1
      ? new Set(
          runs[0].results
            .map((result) => result.chunk_id)
            .filter((chunkId) => runs.every((run) => run.results.some((item) => item.chunk_id === chunkId))),
        )
      : new Set<string>()

  return (
    <div className="page-stack retrieval-page">
      <PageHeader
        title="检索对比"
        description="同一查询并行进入 Dense、BM25、RRF 和重排路径，比较排名漂移、引用来源与耗时。"
        aside={
          <div className="lab-stats">
            <div>
              <span>策略数</span>
              <strong>{strategies.length}</strong>
            </div>
            <div>
              <span>Top K</span>
              <strong>{topK}</strong>
            </div>
          </div>
        }
      />

      <section className="retrieval-querybar">
        <div className="query-input-wrap">
          <span className="query-label">政策问题</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') execute()
            }}
            placeholder="例如：青年人才租房补贴需要什么条件？"
            value={query}
          />
        </div>
        <button
          className="button button-primary button-run"
          disabled={comparison.isPending || !query.trim() || strategies.length === 0}
          onClick={execute}
          type="button"
        >
          <Play size={16} fill="currentColor" />
          {comparison.isPending ? '正在并行检索' : '运行对比'}
        </button>
      </section>

      <section className="retrieval-layout">
        <aside className="panel retrieval-config">
          <div className="panel-heading compact">
            <div>
              <h3>检索配置</h3>
            </div>
          </div>

          <div className="config-group">
            <span className="config-label">切片策略</span>
            <div className="segmented-control">
              {chunkStrategies.map((item) => (
                <button
                  className={chunkStrategy === item.value ? 'is-active' : ''}
                  key={item.value}
                  onClick={() => setChunkStrategy(item.value)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="config-group">
            <div className="config-label-row">
              <span className="config-label">Top K</span>
              <strong className="mono-value">{topK}</strong>
            </div>
            <input
              className="range-input"
              max={10}
              min={1}
              onChange={(event) => setTopK(Number(event.target.value))}
              type="range"
              value={topK}
            />
          </div>

          <div className="config-group">
            <span className="config-label">检索路径</span>
            <div className="toggle-stack">
              {allStrategies.map((item) => (
                <button
                  className={strategies.includes(item.value) ? 'is-active' : ''}
                  key={item.value}
                  onClick={() => toggleStrategy(item.value)}
                  type="button"
                >
                  <span className="toggle-box">{strategies.includes(item.value) ? '✓' : ''}</span>
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.note}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="config-footnote">
            <Waypoints size={16} />
            <p>共同命中用左侧红标记。展开每列可查看 Dense / BM25 rank 与重排变化。</p>
          </div>
        </aside>

        <section className="comparison-area">
          {comparison.isError ? <ErrorState message={comparison.error.message} /> : null}

          {!comparison.data && !comparison.isPending ? (
            <div className="panel comparison-empty">
              <h3>等待一次检索实验</h3>
              <p>运行后会在这里并排显示各策略的候选、分数和引用。</p>
            </div>
          ) : null}

          {comparison.data ? (
            <>
              <div className="comparison-summary">
                <span>
                  <strong>{comparison.data.runs.length}</strong> 条检索路径
                </span>
                <span>
                  <strong>{sharedChunkIds.size}</strong> 个共同命中
                </span>
                <span>
                  <strong>{comparison.data.chunk_strategy}</strong> 切片
                </span>
                {comparison.data.runs[0] ? (
                  <Link className="text-link" to={`/traces/${comparison.data.runs[0].trace_id}`}>
                    查看首条 Trace <ArrowRight size={14} />
                  </Link>
                ) : null}
              </div>

              <div
                className="comparison-board"
                style={{ gridTemplateColumns: `repeat(${comparison.data.runs.length}, minmax(230px, 1fr))` }}
              >
                {comparison.data.runs.map((run) => (
                  <article className="comparison-column" key={run.strategy}>
                    <header className="comparison-head">
                      <div>
                        <h3>{run.label}</h3>
                      </div>
                      <span className="latency-badge">{run.latency_ms.toFixed(1)} ms</span>
                    </header>
                    <div className="result-list">
                      {run.results.map((result) => {
                        const isShared = sharedChunkIds.has(result.chunk_id)
                        const scoreWidth = Math.min(100, Math.max(5, result.score * 100))
                        return (
                          <article
                            className={`result-card${isShared ? ' is-shared' : ''}`}
                            key={result.chunk_id}
                          >
                            <div className="result-rankline">
                              <span className="result-rank">R{result.rank}</span>
                              <span className="result-score">{result.score.toFixed(4)}</span>
                              {isShared ? <span className="shared-flag">共同</span> : null}
                            </div>
                            <h4>{result.heading_path}</h4>
                            <p className="result-document">{result.document_title} · P.{result.page}</p>
                            <p className="result-snippet">{result.text.replace(/\s+/g, ' ')}</p>
                            <div className="result-meter">
                              <span style={{ width: `${scoreWidth}%` }} />
                            </div>
                            <div className="rank-details">
                              <span>D {result.ranks.dense_rank ?? '—'}</span>
                              <span>B {result.ranks.bm25_rank ?? '—'}</span>
                              {result.ranks.rerank_delta !== null ? (
                                <span className={result.ranks.rerank_delta >= 0 ? 'up' : 'down'}>
                                  Δ {result.ranks.rerank_delta > 0 ? '+' : ''}
                                  {result.ranks.rerank_delta}
                                </span>
                              ) : null}
                            </div>
                            <Link className="trace-link" to={`/traces/${run.trace_id}`}>
                              <CornerDownRight size={13} /> Trace
                            </Link>
                          </article>
                        )
                      })}
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}

          {comparison.isPending ? (
            <div className="comparison-loading">
              <p>正在并行执行召回、融合与重排…</p>
            </div>
          ) : null}

          <AnswerPanel
            data={answer.data ?? null}
            disabled={!query.trim()}
            error={answer.error?.message ?? null}
            isPending={answer.isPending}
            onGenerate={generateAnswer}
          />
        </section>
      </section>
    </div>
  )
}
