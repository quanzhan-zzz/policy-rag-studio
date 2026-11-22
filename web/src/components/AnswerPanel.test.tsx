import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { AnswerResponse } from '../types'
import { AnswerPanel } from './AnswerPanel'

const answer: AnswerResponse = {
  query: '青年人才租房补贴的申报条件是什么',
  answer: '申请人需在本市无自有住房。[1]',
  model: 'test-model',
  retrieval: {
    strategy: 'hybrid_rerank',
    label: 'Hybrid + Rerank',
    latency_ms: 12.5,
    trace_id: 'trace-01',
    results: [],
  },
  citations: [
    {
      source_id: 1,
      chunk_id: 'chunk-01',
      document_title: '青年人才租房补贴实施办法',
      heading_path: '第三章 申报条件',
      page: 2,
      text: '申请人及其配偶在本市无自有住房。',
    },
  ],
}

describe('AnswerPanel', () => {
  it('renders the answer and its source register', () => {
    render(
      <MemoryRouter>
        <AnswerPanel
          data={answer}
          disabled={false}
          error={null}
          isPending={false}
          onGenerate={() => undefined}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('申请人需在本市无自有住房。[1]')).toBeInTheDocument()
    expect(screen.getByText('第三章 申报条件')).toBeInTheDocument()
    expect(screen.getByText(/青年人才租房补贴实施办法/)).toBeInTheDocument()
  })

  it('lets the user request an answer', () => {
    const onGenerate = vi.fn()
    render(
      <MemoryRouter>
        <AnswerPanel
          data={null}
          disabled={false}
          error={null}
          isPending={false}
          onGenerate={onGenerate}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: '生成带引用回答' }))
    expect(onGenerate).toHaveBeenCalledOnce()
  })
})
