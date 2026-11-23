import { AlertTriangle, LoaderCircle, Quote, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { AnswerResponse } from '../types'

function normalizeAnswerLine(line: string) {
  return line
    .replace(/^#{1,6}\s+/, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^[-*]\s+/, '• ')
}

type AnswerPanelProps = {
  data: AnswerResponse | null
  disabled: boolean
  error: string | null
  isPending: boolean
  onGenerate: () => void
}

export function AnswerPanel({
  data,
  disabled,
  error,
  isPending,
  onGenerate,
}: AnswerPanelProps) {
  const answerLines =
    data?.answer
      .split('\n')
      .filter((line) => line.trim())
      .map(normalizeAnswerLine) ?? []

  return (
    <article aria-live="polite" className="panel answer-panel">
      <header className="answer-head">
        <div>
          <h3>证据回答</h3>
          <p>基于 Hybrid + Rerank 候选生成，引用编号可回查原文。</p>
        </div>
        <button
          className="button button-answer"
          disabled={disabled || isPending}
          onClick={onGenerate}
          type="button"
        >
          {isPending ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
          {isPending ? '正在生成' : data ? '重新生成' : '生成带引用回答'}
        </button>
      </header>

      {error ? (
        <div className="answer-state is-error">
          <AlertTriangle size={18} />
          <div>
            <strong>回答生成失败</strong>
            <p>{error}</p>
          </div>
        </div>
      ) : null}

      {isPending && !data ? (
        <div className="answer-state">
          <LoaderCircle className="spin" size={18} />
          <div>
            <strong>正在生成回答</strong>
            <p>检索结果编号后作为上下文，回答需逐条引用。</p>
          </div>
        </div>
      ) : null}

      {!data && !isPending && !error ? (
        <div className="answer-state">
          <Quote size={20} />
          <div>
            <strong>尚无回答</strong>
            <p>生成后可在此逐条核对引用与原文。</p>
          </div>
        </div>
      ) : null}

      {data ? (
        <>
          <div className="answer-meta">
            <span><strong>{data.model}</strong></span>
            <span>检索 {data.retrieval.latency_ms.toFixed(1)} ms</span>
            <span>{data.citations.length} 条引用</span>
            {data.first_token_ms ? <span>首字 {data.first_token_ms.toFixed(1)} ms</span> : null}
            {data.total_ms ? <span>总计 {data.total_ms.toFixed(1)} ms</span> : null}
            {data.total_tokens ? (
              <span>
                Token {data.prompt_tokens ?? 0}/{data.completion_tokens ?? 0}
              </span>
            ) : null}
            {data.grounding_status ? <span>{data.grounding_status}</span> : null}
            {data.verification_status && data.verification_status !== 'not_run' ? (
              <span>
                核验 {data.verification_status} · 通过 {data.verified_claim_count ?? 0} 条 · 移除{' '}
                {data.removed_claim_count ?? 0} 条
              </span>
            ) : null}
            {data.verification_fallback_reason ? (
              <span>核验降级 {data.verification_fallback_reason}</span>
            ) : null}
            <Link className="text-link" to={`/traces/${data.retrieval.trace_id}`}>
              查看这次回答的 Trace
            </Link>
          </div>
          {data.invalid_citation_ids?.length ? (
            <div className="answer-citation-warning">
              检测到无效引用：{data.invalid_citation_ids.map((id) => `[${id}]`).join('、')}
            </div>
          ) : null}
          <div className="answer-body">
            <section className="answer-copy">
              <span className="answer-kicker">问题</span>
              <h4>{data.query}</h4>
              <div className="answer-prose">
                {answerLines.map((line, index) => (
                  <p key={`${index}-${line}`}>{line}</p>
                ))}
              </div>
            </section>
            <aside className="answer-citations">
              <div className="answer-citations-head">
                <span className="answer-kicker">引用登记</span>
                <strong>{data.citations.length}</strong>
              </div>
              <div className="answer-citation-list">
                {data.citations.map((citation) => (
                  <article className="answer-citation" key={citation.chunk_id}>
                    <span className="answer-citation-index">[{citation.source_id}]</span>
                    <div>
                      <h5>{citation.heading_path}</h5>
                      <p>{citation.document_title} · P.{citation.page}</p>
                      <blockquote>{citation.text.replace(/\s+/g, ' ')}</blockquote>
                    </div>
                  </article>
                ))}
              </div>
            </aside>
          </div>
        </>
      ) : null}
    </article>
  )
}
