import type {
  AnswerResponse,
  ChunkRecord,
  ChunkStrategy,
  DocumentSummary,
  EvaluationSummary,
  Health,
  IndexTask,
  Overview,
  RetrievalResponse,
  RetrievalStrategy,
  TraceRecord,
  UploadDocumentResponse,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
    ...init,
  })
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: string }
      message = payload.detail ?? message
    } catch {
      // Preserve the generic message for non-JSON errors.
    }
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),
  overview: () => request<Overview>('/overview'),
  documents: () => request<DocumentSummary[]>('/documents'),
  chunks: (documentId: string, strategy: ChunkStrategy) =>
    request<ChunkRecord[]>(`/documents/${documentId}/chunks?strategy=${strategy}`),
  uploadDocument: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<UploadDocumentResponse>('/documents', { method: 'POST', body })
  },
  reindexDocument: (documentId: string) =>
    request<IndexTask>(`/documents/${documentId}/reindex`, { method: 'POST' }),
  indexTask: (taskId: string) => request<IndexTask>(`/indexing/tasks/${taskId}`),
  retryIndexTask: (taskId: string) =>
    request<IndexTask>(`/indexing/tasks/${taskId}/retry`, { method: 'POST' }),
  cancelIndexTask: (taskId: string) =>
    request<IndexTask>(`/indexing/tasks/${taskId}/cancel`, { method: 'POST' }),
  updateChunk: (chunkId: string, text: string) =>
    request<ChunkRecord>(`/chunks/${chunkId}`, {
      method: 'PATCH',
      body: JSON.stringify({ text }),
    }),
  compareRetrieval: (payload: {
    query: string
    strategies: RetrievalStrategy[]
    chunk_strategy: ChunkStrategy
    top_k: number
  }) =>
    request<RetrievalResponse>('/retrieval/compare', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  answer: (payload: {
    query: string
    chunk_strategy: ChunkStrategy
    top_k: number
    temperature?: number
  }) =>
    request<AnswerResponse>('/answer', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  evaluationSummary: () => request<EvaluationSummary>('/evaluations/summary'),
  trace: (traceId: string) => request<TraceRecord>(`/traces/${traceId}`),
}

export { ApiError }

export type AnswerStreamHandlers = {
  onMeta: (data: AnswerResponse) => void
  onDelta: (content: string) => void
  onDone: (data: AnswerResponse) => void
}

export async function streamAnswer(
  payload: {
    query: string
    chunk_strategy: ChunkStrategy
    top_k: number
    temperature?: number
  },
  handlers: AnswerStreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_BASE}/answer/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new ApiError(`请求失败 (${response.status})`, response.status)
  }
  if (!response.body) {
    throw new ApiError('浏览器不支持流式响应', 0)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const eventLine = block.split('\n').find((line) => line.startsWith('event:'))
      const dataLine = block.split('\n').find((line) => line.startsWith('data:'))
      if (!eventLine || !dataLine) continue
      const event = eventLine.slice('event:'.length).trim()
      const data = JSON.parse(dataLine.slice('data:'.length).trim())
      if (event === 'meta') handlers.onMeta(data as AnswerResponse)
      if (event === 'delta') handlers.onDelta(String(data.content ?? ''))
      if (event === 'done') handlers.onDone(data as AnswerResponse)
      if (event === 'error') throw new ApiError(String(data.message ?? '流式回答失败'), 502)
    }
  }
}
