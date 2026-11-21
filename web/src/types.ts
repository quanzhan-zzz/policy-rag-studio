export type ChunkStrategy = 'fixed' | 'heading' | 'recursive'
export type RetrievalStrategy = 'dense' | 'bm25' | 'hybrid' | 'hybrid_rerank'

export type DocumentSummary = {
  id: string
  title: string
  department: string
  file_name: string
  status: string
  effective_date: string
  chunk_count: number
  updated_at: string
  tags: string[]
}

export type ChunkRecord = {
  id: string
  document_id: string
  document_title: string
  strategy: ChunkStrategy
  page: number
  heading_path: string
  text: string
  tokens: number
}

export type RankDetail = {
  dense_rank: number | null
  bm25_rank: number | null
  rerank_delta: number | null
}

export type RetrievedChunk = {
  chunk_id: string
  document_id: string
  document_title: string
  page: number
  heading_path: string
  text: string
  score: number
  rank: number
  citation: string
  ranks: RankDetail
}

export type RetrievalRun = {
  strategy: RetrievalStrategy
  label: string
  latency_ms: number
  trace_id: string
  results: RetrievedChunk[]
}

export type RetrievalResponse = {
  query: string
  chunk_strategy: ChunkStrategy
  top_k: number
  runs: RetrievalRun[]
}

export type TraceStage = {
  key: string
  label: string
  duration_ms: number
  input_count: number | null
  output_count: number | null
  detail: string
}

export type TraceRecord = {
  id: string
  query: string
  strategy: RetrievalStrategy
  chunk_strategy: ChunkStrategy
  total_ms: number
  created_at: string
  stages: TraceStage[]
}

export type MetricRow = {
  strategy: RetrievalStrategy
  label: string
  recall_at_5: number
  mrr: number
  ndcg_at_5: number
  p95_ms: number
}

export type FailureBucket = {
  type: string
  count: number
}

export type EvaluationSummary = {
  dataset_name: string
  case_count: number
  rows: MetricRow[]
  failures: FailureBucket[]
  generated_at: string
}

export type Overview = {
  service_status: string
  document_count: number
  chunk_count: number
  evaluation_case_count: number
  retrieval_runs: number
  model_provider: string
  vector_backend: string
  last_evaluation: EvaluationSummary | null
}

export type Health = {
  status: string
  service: string
  mode: string
}
