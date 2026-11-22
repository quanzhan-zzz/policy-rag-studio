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
