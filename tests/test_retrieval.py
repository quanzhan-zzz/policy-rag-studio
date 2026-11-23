import pytest

from app.schemas import ChunkStrategy, RetrievalFilters, RetrievalStrategy
from app.services.embedding import HashEmbeddingProvider
from app.services.retrieval import run_retrieval
from app.store import InMemoryStore


@pytest.mark.asyncio
async def test_hybrid_returns_ranked_results() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, trace = run_retrieval(
        chunks=chunks,
        query="个体工商户登记需要哪些申请材料",
        strategy=RetrievalStrategy.HYBRID,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=5,
        embedding_provider=HashEmbeddingProvider(),
    )
    assert run.results
    assert run.results[0].document_id == "individual-registration"
    assert any("申请材料" in result.heading_path for result in run.results)
    assert any(stage.key == "rrf" for stage in trace.stages)
    dense_stage = next(stage for stage in trace.stages if stage.key == "dense")
    assert "Hash embedding" in dense_stage.detail


@pytest.mark.asyncio
async def test_all_strategies_return_results() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    for strategy in RetrievalStrategy:
        run, _ = run_retrieval(
            chunks=chunks,
            query="营业执照变更办理时限",
            strategy=strategy,
            chunk_strategy=ChunkStrategy.HEADING,
            top_k=3,
            embedding_provider=HashEmbeddingProvider(),
        )
        assert len(run.results) == 3


@pytest.mark.asyncio
async def test_in_memory_filter_orders_newer_source_first() -> None:
    from datetime import UTC, datetime

    store = InMemoryStore(seed_demo_data=False, seed_official_data=False)
    store._create_document(
        document_id="old-policy",
        title="旧版政策",
        department="测试部门",
        file_name="old.md",
        effective_date="2025-01-01",
        tags=["旧版"],
        text="# 旧版政策\n\n一、办理时限\n10个工作日。",
        region="常州市",
        item_type="测试事项",
        source_name="测试来源",
        source_url="https://example.com/old",
        source_retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    store._create_document(
        document_id="new-policy",
        title="新版政策",
        department="测试部门",
        file_name="new.md",
        effective_date="2026-01-01",
        tags=["新版"],
        text="# 新版政策\n\n一、办理时限\n3个工作日。",
        region="常州市",
        item_type="测试事项",
        source_name="测试来源",
        source_url="https://example.com/new",
        source_retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    chunks = await store.all_chunks(
        ChunkStrategy.HEADING,
        filters=RetrievalFilters(
            region="常州市",
            item_type="测试事项",
            official_only=True,
        ),
    )

    assert chunks
    assert chunks[0].document_id == "new-policy"
