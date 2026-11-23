import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  ChunkStrategy,
  QueryPlanningMode,
  RetrievalFilters,
  RetrievalStrategy,
} from '../types'
import { api } from './api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
  })
}

export function useOverview() {
  return useQuery({ queryKey: ['overview'], queryFn: api.overview })
}

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: api.documents,
    refetchInterval: (query) => {
      const documents = query.state.data
      const active = documents?.some((document) =>
        ['queued', 'parsing', 'chunking', 'embedding'].includes(document.status),
      )
      return active ? 1_500 : false
    },
  })
}

export function useIndexTask(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ['index-task', taskId],
    queryFn: () => api.indexTask(taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ['queued', 'parsing', 'chunking', 'embedding'].includes(status)
        ? 1_500
        : false
    },
  })
}

export function useChunks(documentId: string | undefined, strategy: ChunkStrategy) {
  return useQuery({
    queryKey: ['chunks', documentId, strategy],
    queryFn: () => api.chunks(documentId!, strategy),
    enabled: Boolean(documentId),
  })
}

export function useEvaluation() {
  return useQuery({ queryKey: ['evaluation'], queryFn: api.evaluationSummary })
}

export function useTrace(traceId: string | undefined) {
  return useQuery({
    queryKey: ['trace', traceId],
    queryFn: () => api.trace(traceId!),
    enabled: Boolean(traceId),
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.uploadDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
    },
  })
}

export function useReindexDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.reindexDocument,
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['index-task', task.id] })
    },
  })
}

export function useRetryIndexTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.retryIndexTask,
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['index-task', task.id] })
    },
  })
}

export function useCancelIndexTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.cancelIndexTask,
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['index-task', task.id] })
    },
  })
}

export function useUpdateChunk() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ chunkId, text }: { chunkId: string; text: string }) =>
      api.updateChunk(chunkId, text),
    onSuccess: (chunk) => {
      void queryClient.invalidateQueries({
        queryKey: ['chunks', chunk.document_id, chunk.strategy],
      })
    },
  })
}

export function useAnswer() {
  return useMutation({
    mutationFn: (payload: {
      query: string
      chunk_strategy: ChunkStrategy
      top_k: number
      temperature?: number
      filters?: RetrievalFilters
      query_planning_mode?: QueryPlanningMode
    }) => api.answer(payload),
  })
}

export function useCompareRetrieval() {
  return useMutation({
    mutationFn: (payload: {
      query: string
      strategies: RetrievalStrategy[]
      chunk_strategy: ChunkStrategy
      top_k: number
      filters?: RetrievalFilters
    }) => api.compareRetrieval(payload),
  })
}
