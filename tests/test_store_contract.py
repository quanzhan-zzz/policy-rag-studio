import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from app.db.postgres import PostgresStore
from app.schemas import ChunkStrategy, RetrievalStrategy, TraceRecord, TraceStage
from app.store import InMemoryStore, Store


@pytest_asyncio.fixture(params=["memory", "postgres"])
async def store(request: pytest.FixtureRequest):
    if request.param == "memory":
        yield InMemoryStore()
        return
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL 未配置")
    postgres_store = await PostgresStore.create(database_url, seed_demo_data=False)
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

    assert document.status == "indexed"
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
