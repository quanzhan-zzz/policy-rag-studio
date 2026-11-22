from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IndexTaskStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IndexTaskKind(StrEnum):
    INGEST = "ingest"
    REINDEX = "reindex"


class ChunkStrategy(StrEnum):
    FIXED = "fixed"
    HEADING = "heading"
    RECURSIVE = "recursive"


class RetrievalStrategy(StrEnum):
    DENSE = "dense"
    BM25 = "bm25"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid_rerank"


class DocumentSummary(BaseModel):
    id: str
    title: str
    department: str
    file_name: str
    status: str
    effective_date: str
    chunk_count: int
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    index_task_id: str | None = None
    index_progress: int = Field(default=0, ge=0, le=100)
    index_error: str | None = None


class IndexTask(BaseModel):
    id: str
    document_id: str
    kind: IndexTaskKind
    status: IndexTaskStatus
    progress: int = Field(ge=0, le=100)
    attempts: int = Field(ge=0)
    error_code: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class UploadDocumentResponse(BaseModel):
    document: DocumentSummary
    task: IndexTask


class ChunkRecord(BaseModel):
    id: str
    document_id: str
    document_title: str
    strategy: ChunkStrategy
    page: int
    heading_path: str
    text: str
    tokens: int


class ChunkUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    strategies: list[RetrievalStrategy] = Field(
        default_factory=lambda: [
            RetrievalStrategy.DENSE,
            RetrievalStrategy.BM25,
            RetrievalStrategy.HYBRID,
            RetrievalStrategy.HYBRID_RERANK,
        ]
    )
    chunk_strategy: ChunkStrategy = ChunkStrategy.HEADING
    top_k: int = Field(default=5, ge=1, le=20)


class RankDetail(BaseModel):
    dense_rank: int | None = None
    bm25_rank: int | None = None
    rerank_delta: int | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    page: int
    heading_path: str
    text: str
    score: float
    rank: int
    citation: str
    ranks: RankDetail = Field(default_factory=RankDetail)


class RetrievalRun(BaseModel):
    strategy: RetrievalStrategy
    label: str
    latency_ms: float
    trace_id: str
    results: list[RetrievedChunk]


class RetrievalResponse(BaseModel):
    query: str
    chunk_strategy: ChunkStrategy
    top_k: int
    runs: list[RetrievalRun]


class AnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    chunk_strategy: ChunkStrategy = ChunkStrategy.HEADING
    top_k: int = Field(default=5, ge=1, le=10)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)


class AnswerCitation(BaseModel):
    source_id: int
    chunk_id: str
    document_title: str
    heading_path: str
    page: int
    text: str


class AnswerResponse(BaseModel):
    query: str
    answer: str
    model: str
    retrieval: RetrievalRun
    citations: list[AnswerCitation]


class TraceStage(BaseModel):
    key: str
    label: str
    duration_ms: float
    input_count: int | None = None
    output_count: int | None = None
    detail: str


class TraceRecord(BaseModel):
    id: str
    query: str
    strategy: RetrievalStrategy
    chunk_strategy: ChunkStrategy
    total_ms: float
    created_at: datetime
    stages: list[TraceStage]


class MetricRow(BaseModel):
    strategy: RetrievalStrategy
    label: str
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    p95_ms: float


class FailureBucket(BaseModel):
    type: str
    count: int


class EvaluationSummary(BaseModel):
    id: str | None = None
    dataset_name: str
    split: str | None = None
    reranker_provider: str | None = None
    case_count: int
    rows: list[MetricRow]
    failures: list[FailureBucket]
    generated_at: datetime


class OverviewResponse(BaseModel):
    service_status: str
    document_count: int
    chunk_count: int
    evaluation_case_count: int
    retrieval_runs: int
    model_provider: str
    llm_provider: str
    vector_backend: str
    last_evaluation: EvaluationSummary | None = None
