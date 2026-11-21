from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.schemas import (
    ChunkRecord,
    ChunkStrategy,
    ChunkUpdate,
    DocumentSummary,
    EvaluationSummary,
    OverviewResponse,
    RetrievalRequest,
    RetrievalResponse,
    TraceRecord,
)
from app.services.evaluation import evaluate_store
from app.services.parsing import UnsupportedDocumentError
from app.services.retrieval import run_retrieval
from app.store import store

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "policy-rag-studio", "mode": "in-memory-demo"}


@router.get("/overview", response_model=OverviewResponse)
def overview() -> OverviewResponse:
    evaluation = evaluate_store(store)
    return OverviewResponse(
        service_status="operational",
        document_count=len(store.list_documents()),
        chunk_count=store.count_chunks(),
        evaluation_case_count=evaluation.case_count,
        retrieval_runs=store.retrieval_runs,
        model_provider="Hash embedding · Demo adapter",
        vector_backend="PostgreSQL + pgvector · interface ready",
        last_evaluation=evaluation,
    )


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    return store.list_documents()


@router.post("/documents", response_model=DocumentSummary, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Query()] = None,
) -> DocumentSummary:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    try:
        return store.add_upload(file.filename or "upload.txt", content, title=title)
    except UnsupportedDocumentError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/documents/{document_id}/reindex", response_model=DocumentSummary)
def reindex_document(document_id: str) -> DocumentSummary:
    document = store.reindex_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRecord])
def list_chunks(
    document_id: str,
    strategy: Annotated[ChunkStrategy, Query()] = ChunkStrategy.HEADING,
) -> list[ChunkRecord]:
    if store.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return store.list_chunks(document_id, strategy)


@router.patch("/chunks/{chunk_id}", response_model=ChunkRecord)
def update_chunk(chunk_id: str, payload: ChunkUpdate) -> ChunkRecord:
    chunk = store.update_chunk(chunk_id, payload.text)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk 不存在")
    return chunk


@router.post("/retrieval/compare", response_model=RetrievalResponse)
def compare_retrieval(payload: RetrievalRequest) -> RetrievalResponse:
    chunks = store.all_chunks(payload.chunk_strategy)
    if not chunks:
        raise HTTPException(status_code=400, detail="当前切片策略下没有可检索内容")
    runs = []
    for strategy in payload.strategies:
        run, trace = run_retrieval(
            chunks=chunks,
            query=payload.query,
            strategy=strategy,
            chunk_strategy=payload.chunk_strategy,
            top_k=payload.top_k,
        )
        store.record_trace(trace)
        runs.append(run)
    return RetrievalResponse(
        query=payload.query,
        chunk_strategy=payload.chunk_strategy,
        top_k=payload.top_k,
        runs=runs,
    )


@router.get("/traces/{trace_id}", response_model=TraceRecord)
def get_trace(trace_id: str) -> TraceRecord:
    trace = store.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return trace


@router.get("/evaluations/summary", response_model=EvaluationSummary)
def evaluation_summary() -> EvaluationSummary:
    return evaluate_store(store)
