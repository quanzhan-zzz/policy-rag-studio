export type ChunkStrategy = 'fixed' | 'heading' | 'recursive'
export type IndexTaskStatus =
  | 'queued'
  | 'parsing'
  | 'chunking'
  | 'embedding'
  | 'ready'
  | 'failed'
  | 'cancelled'
export type RetrievalStrategy = 'dense' | 'bm25' | 'hybrid' | 'hybrid_rerank'

export type QueryPlanningMode = 'none' | 'rewrite' | 'decompose'

export type RetrievalFilters = {
  region?: string
  item_type?: string
  department?: string
  official_only?: boolean
  effective_from?: string
  effective_to?: string
  retrieved_from?: string
  retrieved_to?: string
}

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
  index_task_id: string | null
  index_progress: number
  index_error: string | null
  source_name: string | null
  source_url: string | null
  source_retrieved_at: string | null
  source_sha256: string | null
  region: string | null
  item_type: string | null
}

export type IndexTask = {
  id: string
  document_id: string
  kind: 'ingest' | 'reindex'
  status: IndexTaskStatus
  progress: number
  attempts: number
  error_code: string | null
  error_message: string | null
  cancel_requested: boolean
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export type UploadDocumentResponse = {
  document: DocumentSummary
  task: IndexTask
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
  filters?: RetrievalFilters | null
  runs: RetrievalRun[]
}

export type AnswerCitation = {
  source_id: number
  chunk_id: string
  document_id: string
  document_title: string
  heading_path: string
  page: number
  text: string
}

export type AnswerResponse = {
  query: string
  answer: string
  model: string
  retrieval: RetrievalRun
  citations: AnswerCitation[]
  first_token_ms?: number | null
  total_ms?: number | null
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  invalid_citation_ids?: number[]
  grounding_status?: string
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
  id?: string
  dataset_name: string
  split?: string | null
  reranker_provider?: string | null
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
  llm_provider: string
  vector_backend: string
  last_evaluation: EvaluationSummary | null
}

export type Health = {
  status: string
  service: string
  mode: string
}
