import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.dependencies import get_store, get_task_publisher
from app.schemas import (
    AnswerRequest,
    AnswerResponse,
    ChunkRecord,
    ChunkStrategy,
    ChunkUpdate,
    DocumentSummary,
    EvaluationSummary,
    IndexTask,
    IndexTaskStatus,
    OverviewResponse,
    RetrievalRequest,
    RetrievalResponse,
    TraceRecord,
    UploadDocumentResponse,
)
from app.services.answer import answer_query, stream_answer_query
from app.services.embedding import get_embedding_provider
from app.services.evaluation import evaluate_store
from app.services.evaluation_dataset import get_evaluation_dataset
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.parsing import UnsupportedDocumentError, validate_document_type
from app.services.retrieval import prepare_dense_scores, run_retrieval
from app.services.task_publisher import TaskPublisher
from app.store import Store

router = APIRouter(prefix="/api/v1")
StoreDep = Annotated[Store, Depends(get_store)]
PublisherDep = Annotated[TaskPublisher, Depends(get_task_publisher)]


async def _publish_or_fail(store: Store, publisher: TaskPublisher, task_id: str) -> None:
    try:
        await asyncio.to_thread(publisher.enqueue_index, task_id)
    except Exception as error:
        await store.transition_index_task(
            task_id,
            IndexTaskStatus.FAILED,
            0,
            error_code="queue_unavailable",
            error_message="索引队列暂时不可用",
        )
        raise HTTPException(status_code=503, detail="索引队列暂时不可用") from error


@router.get("/health")
async def health(store: StoreDep) -> dict[str, str]:
    online = await store.ping()
    return {
        "status": "ok" if online else "degraded",
        "service": "policy-rag-studio",
        "mode": store.backend,
        "version": get_settings().app_version,
    }


@router.get("/overview", response_model=OverviewResponse)
async def overview(store: StoreDep) -> OverviewResponse:
    evaluation = await store.get_latest_evaluation()
    if evaluation is None:
        evaluation = await store.record_evaluation(await evaluate_store(store))
    return OverviewResponse(
        service_status="operational" if await store.ping() else "degraded",
        document_count=len(await store.list_documents()),
        chunk_count=await store.count_chunks(),
        evaluation_case_count=evaluation.case_count,
        retrieval_runs=await store.count_retrieval_runs(),
        model_provider=get_embedding_provider().name,
        llm_provider=get_llm_provider().name,
        vector_backend="PostgreSQL + pgvector · HNSW cosine index",
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


@router.post("/documents", response_model=UploadDocumentResponse, status_code=202)
async def upload_document(
    file: Annotated[UploadFile, File()],
    store: StoreDep,
    publisher: PublisherDep,
    title: Annotated[str | None, Query()] = None,
) -> UploadDocumentResponse:
    file_name = file.filename or "upload.txt"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    try:
        validate_document_type(file_name)
        document, task = await store.create_upload_task(file_name, content, title=title)
    except UnsupportedDocumentError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    await _publish_or_fail(store, publisher, task.id)
    return UploadDocumentResponse(document=document, task=task)


@router.post("/documents/{document_id}/reindex", response_model=IndexTask)
async def reindex_document(
    document_id: str,
    store: StoreDep,
    publisher: PublisherDep,
) -> IndexTask:
    task = await store.create_reindex_task(document_id)
    if task is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    await _publish_or_fail(store, publisher, task.id)
    return task


@router.get("/indexing/tasks/{task_id}", response_model=IndexTask)
async def get_index_task(task_id: str, store: StoreDep) -> IndexTask:
    task = await store.get_index_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="索引任务不存在")
    return task


@router.post("/indexing/tasks/{task_id}/cancel", response_model=IndexTask)
async def cancel_index_task(task_id: str, store: StoreDep) -> IndexTask:
    task = await store.request_cancel_index_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="索引任务不存在")
    return task


@router.post("/indexing/tasks/{task_id}/retry", response_model=IndexTask)
async def retry_index_task(
    task_id: str,
    store: StoreDep,
    publisher: PublisherDep,
) -> IndexTask:
    task = await store.retry_index_task(task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="只有失败或已取消的任务可以重试")
    await _publish_or_fail(store, publisher, task.id)
    return task


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
    embedding_provider, dense_scores, dense_latency_ms = await prepare_dense_scores(
        store,
        chunks,
        payload.query,
        payload.chunk_strategy,
    )
    runs = []
    for strategy in payload.strategies:
        run, trace = await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=payload.query,
            strategy=strategy,
            chunk_strategy=payload.chunk_strategy,
            top_k=payload.top_k,
            embedding_provider=embedding_provider,
            dense_scores_by_chunk=dense_scores,
            precomputed_latency_ms=dense_latency_ms,
        )
        await store.record_trace(trace)
        runs.append(run)
    return RetrievalResponse(
        query=payload.query,
        chunk_strategy=payload.chunk_strategy,
        top_k=payload.top_k,
        runs=runs,
    )


@router.post("/answer/stream")
async def answer_stream(payload: AnswerRequest, store: StoreDep) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            async for event in stream_answer_query(store, payload):
                payload_text = json.dumps(event.data, ensure_ascii=False)
                yield f"event: {event.event}\ndata: {payload_text}\n\n"
        except Exception as error:
            data = {
                "message": str(error),
                "error_type": type(error).__name__,
            }
            yield f"event: error\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
async def evaluation_summary(
    store: StoreDep,
    dataset: Annotated[
        str,
        Query(pattern="^(smoke|policy-synthetic-v1)$"),
    ] = "policy-synthetic-v1",
    split: Annotated[str, Query(pattern="^(dev|test|all)$")] = "test",
) -> EvaluationSummary:
    try:
        evaluation_set = get_evaluation_dataset(dataset, split)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    evaluation = await evaluate_store(
        store,
        cases=evaluation_set.cases,
        dataset_name=evaluation_set.name,
        split=evaluation_set.split,
    )
    return await store.record_evaluation(evaluation)
