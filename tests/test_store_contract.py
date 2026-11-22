import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import (
    ChunkStrategy,
    EvaluationSummary,
    FailureBucket,
    IndexTaskStatus,
    MetricRow,
    RetrievalStrategy,
    TraceRecord,
    TraceStage,
)
from app.services.chunking import chunk_document
from app.services.embedding import HashEmbeddingProvider
from app.store import InMemoryStore, Store


@pytest_asyncio.fixture(params=["memory", "postgres"])
async def store(request: pytest.FixtureRequest):
    if request.param == "memory":
        yield InMemoryStore()
        return
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL 未配置")
    postgres_store = await PostgresStore.create(
        database_url,
        seed_demo_data=False,
        initialize_schema=True,
    )
    try:
        yield postgres_store
    finally:
        await postgres_store.close()


async def _assert_document_lifecycle(store: Store) -> None:
    suffix = uuid4().hex[:8]
    document = await store.add_upload(
        f"contract-{suffix}.md",
        (
            "# 合同测试政策\n\n一、适用范围\n用于验证仓储契约。"
            "\n\n二、办理流程\n申请人提交材料。"
        ).encode(),
        title=f"仓储契约测试 {suffix}",
    )

    assert document.status == "ready"
    assert document.chunk_count > 0
    assert await store.get_document(document.id) == document

    for strategy in ChunkStrategy:
        chunks = await store.list_chunks(document.id, strategy)
        assert chunks
        assert all(chunk.document_id == document.id for chunk in chunks)

    heading_chunks = await store.list_chunks(document.id, ChunkStrategy.HEADING)
    updated = await store.update_chunk(
        heading_chunks[0].id,
        "一、适用范围\n已编辑的仓储契约内容。",
    )
    assert updated is not None
    assert updated.text.startswith("一、适用范围")
    assert updated.tokens > 0

    settings = get_settings()
    provider = HashEmbeddingProvider(dimensions=settings.hash_embedding_dimensions)
    dense_scores = await store.dense_scores(
        ChunkStrategy.HEADING,
        provider.embed_query(updated.text),
    )
    scores_by_id = dict(dense_scores)
    assert {chunk.id for chunk in heading_chunks}.issubset(scores_by_id)
    assert scores_by_id[updated.id] == max(scores_by_id.values())

    before_reindex = len(await store.list_chunks(document.id, ChunkStrategy.HEADING))
    reindexed = await store.reindex_document(document.id)
    assert reindexed is not None
    assert len(await store.list_chunks(document.id, ChunkStrategy.HEADING)) == before_reindex


@pytest.mark.asyncio
async def test_store_document_and_chunk_contract(store: Store) -> None:
    await _assert_document_lifecycle(store)


@pytest.mark.asyncio
async def test_store_trace_contract(store: Store) -> None:
    before = await store.count_retrieval_runs()
    trace_id = f"trace-contract-{uuid4().hex[:8]}"
    trace = TraceRecord(
        id=trace_id,
        query="仓储契约查询",
        strategy=RetrievalStrategy.HYBRID,
        chunk_strategy=ChunkStrategy.HEADING,
        total_ms=1.25,
        created_at=datetime.now(UTC),
        stages=[
            TraceStage(
                key="retrieve",
                label="检索",
                duration_ms=1.25,
                input_count=1,
                output_count=1,
                detail="contract test",
            )
        ],
    )

    await store.record_trace(trace)
    assert await store.get_trace(trace_id) == trace
    assert await store.count_retrieval_runs() == before + 1


@pytest.mark.asyncio
async def test_store_evaluation_contract(store: Store) -> None:
    evaluation = EvaluationSummary(
        dataset_name="contract-eval",
        case_count=1,
        rows=[
            MetricRow(
                strategy=RetrievalStrategy.HYBRID,
                label="Hybrid",
                recall_at_5=1.0,
                mrr=1.0,
                ndcg_at_5=1.0,
                p95_ms=1.0,
            )
        ],
        failures=[FailureBucket(type="contract", count=0)],
        generated_at=datetime.now(UTC),
    )

    stored = await store.record_evaluation(evaluation)
    assert stored.id
    latest = await store.get_latest_evaluation()
    assert latest is not None
    assert latest.id == stored.id
    assert latest.rows[0].strategy is RetrievalStrategy.HYBRID


@pytest.mark.asyncio
async def test_store_index_task_contract(store: Store) -> None:
    content = (
        "# 异步索引契约\n\n"
        "一、适用范围\n用于验证任务状态转换。\n\n"
        "二、办理流程\n提交材料后等待审核。"
    ).encode()
    document, task = await store.create_upload_task(
        f"async-{uuid4().hex[:8]}.md",
        content,
        title="异步索引契约测试",
    )
    assert document.status == IndexTaskStatus.QUEUED.value
    assert document.index_task_id == task.id
    assert not await store.list_chunks(document.id, ChunkStrategy.HEADING)

    claimed = await store.claim_index_task(task.id)
    assert claimed is not None
    assert claimed.status is IndexTaskStatus.PARSING
    assert claimed.attempts == 1
    assert await store.claim_index_task(task.id) is None

    transitioned = await store.transition_index_task(
        task.id,
        IndexTaskStatus.CHUNKING,
        35,
    )
    assert transitioned is not None
    assert transitioned.progress == 35

    source = await store.get_document_source(document.id)
    assert source is not None
    assert source.source_content == content

    chunks = chunk_document(
        content.decode(),
        document.id,
        document.title,
        ChunkStrategy.HEADING,
    )
    provider = HashEmbeddingProvider(dimensions=get_settings().hash_embedding_dimensions)
    vectors = provider.embed_documents([chunk.text for chunk in chunks])
    await store.transition_index_task(task.id, IndexTaskStatus.EMBEDDING, 65)
    await store.apply_document_index(
        document.id,
        content.decode(),
        chunks,
        {chunk.id: vector for chunk, vector in zip(chunks, vectors, strict=True)},
    )
    ready = await store.transition_index_task(task.id, IndexTaskStatus.READY, 100)
    assert ready is not None
    assert ready.status is IndexTaskStatus.READY
    final_document = await store.get_document(document.id)
    assert final_document is not None
    assert final_document.status == IndexTaskStatus.READY.value

    first_reindex = await store.create_reindex_task(document.id)
    second_reindex = await store.create_reindex_task(document.id)
    assert first_reindex is not None
    assert second_reindex is not None
    assert first_reindex.id == second_reindex.id

    cancelled = await store.request_cancel_index_task(first_reindex.id)
    assert cancelled is not None
    assert cancelled.status is IndexTaskStatus.CANCELLED
    retried = await store.retry_index_task(first_reindex.id)
    assert retried is not None
    assert retried.status is IndexTaskStatus.QUEUED


@pytest.mark.asyncio
async def test_stale_processing_task_can_be_reclaimed(store: Store) -> None:
    document, task = await store.create_upload_task(
        f"stale-{uuid4().hex[:8]}.md",
        b"# stale task\n\nfailed worker recovery",
        title="Stale task",
    )
    first = await store.claim_index_task(task.id)
    second = await store.claim_index_task(task.id)
    stale = await store.list_stale_index_tasks(stale_after_seconds=0)
    assert any(item.id == task.id for item in stale)
    reclaimed = await store.claim_index_task(task.id, stale_after_seconds=0)
    assert first is not None
    assert second is None
    assert reclaimed is not None
    assert reclaimed.attempts == 2
    current = await store.get_document(document.id)
    assert current is not None
    assert current.index_task_id == task.id
