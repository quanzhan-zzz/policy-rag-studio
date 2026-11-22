import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.dependencies import get_store
from app.schemas import (
    AnswerRequest,
    AnswerResponse,
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
from app.services.answer import answer_query
from app.services.embedding import get_embedding_provider
from app.services.evaluation import evaluate_store
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.parsing import UnsupportedDocumentError
from app.services.retrieval import run_retrieval
from app.store import Store

router = APIRouter(prefix="/api/v1")
StoreDep = Annotated[Store, Depends(get_store)]


@router.get("/health")
async def health(store: StoreDep) -> dict[str, str]:
    online = await store.ping()
    return {
        "status": "ok" if online else "degraded",
        "service": "policy-rag-studio",
        "mode": store.backend,
    }


@router.get("/overview", response_model=OverviewResponse)
async def overview(store: StoreDep) -> OverviewResponse:
    evaluation = await evaluate_store(store)
    return OverviewResponse(
        service_status="operational" if await store.ping() else "degraded",
        document_count=len(await store.list_documents()),
        chunk_count=await store.count_chunks(),
        evaluation_case_count=evaluation.case_count,
        retrieval_runs=await store.count_retrieval_runs(),
        model_provider=get_embedding_provider().name,
        llm_provider=get_llm_provider().name,
        vector_backend="PostgreSQL · documents persisted / pgvector pending",
        last_evaluation=evaluation,
    )


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(store: StoreDep) -> list[DocumentSummary]:
    return await store.list_documents()


@router.get("/documents/{document_id}", response_model=DocumentSummary)
async def get_document(document_id: str, store: StoreDep) -> DocumentSummary:
    document = await store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.post("/documents", response_model=DocumentSummary, status_code=201)
async def upload_document(
    file: Annotated[UploadFile, File()],
    store: StoreDep,
    title: Annotated[str | None, Query()] = None,
) -> DocumentSummary:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    try:
        return await store.add_upload(file.filename or "upload.txt", content, title=title)
    except UnsupportedDocumentError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/documents/{document_id}/reindex", response_model=DocumentSummary)
async def reindex_document(document_id: str, store: StoreDep) -> DocumentSummary:
    document = await store.reindex_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRecord])
async def list_chunks(
    document_id: str,
    store: StoreDep,
    strategy: Annotated[ChunkStrategy, Query()] = ChunkStrategy.HEADING,
) -> list[ChunkRecord]:
    if await store.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return await store.list_chunks(document_id, strategy)


@router.patch("/chunks/{chunk_id}", response_model=ChunkRecord)
async def update_chunk(chunk_id: str, payload: ChunkUpdate, store: StoreDep) -> ChunkRecord:
    chunk = await store.update_chunk(chunk_id, payload.text)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk 不存在")
    return chunk


@router.post("/retrieval/compare", response_model=RetrievalResponse)
async def compare_retrieval(payload: RetrievalRequest, store: StoreDep) -> RetrievalResponse:
    chunks = await store.all_chunks(payload.chunk_strategy)
    if not chunks:
        raise HTTPException(status_code=400, detail="当前切片策略下没有可检索内容")
    runs = []
    for strategy in payload.strategies:
        run, trace = await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=payload.query,
            strategy=strategy,
            chunk_strategy=payload.chunk_strategy,
            top_k=payload.top_k,
        )
        await store.record_trace(trace)
        runs.append(run)
    return RetrievalResponse(
        query=payload.query,
        chunk_strategy=payload.chunk_strategy,
        top_k=payload.top_k,
        runs=runs,
    )


@router.post("/answer", response_model=AnswerResponse)
async def answer(payload: AnswerRequest, store: StoreDep) -> AnswerResponse:
    try:
        return await answer_query(store, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LLMProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/traces/{trace_id}", response_model=TraceRecord)
async def get_trace(trace_id: str, store: StoreDep) -> TraceRecord:
    trace = await store.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return trace


@router.get("/evaluations/summary", response_model=EvaluationSummary)
async def evaluation_summary(store: StoreDep) -> EvaluationSummary:
    return await evaluate_store(store)
