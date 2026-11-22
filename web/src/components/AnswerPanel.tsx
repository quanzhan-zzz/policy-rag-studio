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
          <span className="panel-index">C / ANSWER WITH EVIDENCE</span>
          <h3>让模型只根据证据回答</h3>
          <p>使用 Hybrid + Rerank 的 Top-K 候选组装 Context Pack，回答中的编号可以直接回看原文。</p>
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
          <span className="scan-line" />
          <LoaderCircle className="spin" size={18} />
          <div>
            <strong>正在组装上下文并调用文本模型</strong>
            <p>检索结果会先编号，再要求模型逐条引用；当前不会把整个知识库交给模型。</p>
          </div>
        </div>
      ) : null}

      {!data && !isPending && !error ? (
        <div className="answer-state">
          <Quote size={20} />
          <div>
            <strong>检索完成后，生成一份可核验回答</strong>
            <p>先生成回答，再逐条检查引用，确认模型是否忠实于政策原文。</p>
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
              <span className="answer-kicker">QUESTION</span>
              <h4>{data.query}</h4>
              <div className="answer-prose">
                {answerLines.map((line, index) => (
                  <p key={`${index}-${line}`}>{line}</p>
                ))}
              </div>
            </section>
            <aside className="answer-citations">
              <div className="answer-citations-head">
                <span className="answer-kicker">SOURCE REGISTER</span>
                <strong>{data.citations.length.toString().padStart(2, '0')}</strong>
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
