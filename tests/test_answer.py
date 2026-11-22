import pytest

from app.schemas import AnswerRequest, ChunkStrategy, RetrievalStrategy
from app.services.answer import answer_query, build_context
from app.services.retrieval import run_retrieval
from app.store import InMemoryStore


class FakeLLM:
    name = "fake-llm"

    def chat(self, messages, *, temperature=0.1, max_tokens=800):
        assert messages
        assert temperature == 0.1
        return "办理地点是常州市政务服务中心。[1]"


@pytest.mark.asyncio
async def test_build_context_numbers_citations() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, _ = run_retrieval(
        chunks=chunks,
        query="办理地点",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=3,
    )
    context, citations = build_context(run.results)
    assert "[1]" in context
    assert citations[0].source_id == 1
    assert citations[0].chunk_id == run.results[0].chunk_id


@pytest.mark.asyncio
async def test_answer_query_uses_injected_provider() -> None:
    store = InMemoryStore()
    response = await answer_query(
        store,
        AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=3),
        llm_provider=FakeLLM(),
    )
    assert response.query == "青年人才租房补贴在哪里办理"
    assert response.model == "fake-llm"
    assert "[1]" in response.answer
    assert response.citations
