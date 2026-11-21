from app.schemas import ChunkStrategy, RetrievalStrategy
from app.services.embedding import HashEmbeddingProvider
from app.services.retrieval import run_retrieval
from app.store import InMemoryStore


def test_hybrid_returns_ranked_results() -> None:
    store = InMemoryStore()
    chunks = store.all_chunks(ChunkStrategy.HEADING)
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


def test_all_strategies_return_results() -> None:
    store = InMemoryStore()
    chunks = store.all_chunks(ChunkStrategy.HEADING)
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
