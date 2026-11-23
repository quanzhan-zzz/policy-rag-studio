import { useCallback, useState } from 'react'

import type {
  AnswerResponse,
  ChunkStrategy,
  CitationVerifierProvider,
  QueryPlanningMode,
  RetrievalFilters,
} from '../types'
import { streamAnswer } from './api'

type AnswerPayload = {
  query: string
  chunk_strategy: ChunkStrategy
  top_k: number
  temperature?: number
  filters?: RetrievalFilters
  query_planning_mode?: QueryPlanningMode
  citation_verifier_provider?: CitationVerifierProvider
}

export function useAnswerStream() {
  const [data, setData] = useState<AnswerResponse | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isPending, setIsPending] = useState(false)

  const start = useCallback(async (payload: AnswerPayload) => {
    setData(null)
    setError(null)
    setIsPending(true)
    let current: AnswerResponse | null = null
    try {
      await streamAnswer(payload, {
        onMeta: (meta) => {
          current = { ...meta, answer: '' }
          setData(current)
        },
        onDelta: (content) => {
          if (!current) return
          current = { ...current, answer: current.answer + content }
          setData(current)
        },
        onDone: (done) => {
          current = done
          setData(done)
        },
      })
    } catch (streamError) {
      setError(streamError instanceof Error ? streamError : new Error('流式回答失败'))
    } finally {
      setIsPending(false)
    }
  }, [])

  return { data, error, isPending, start }
}
