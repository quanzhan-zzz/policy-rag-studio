import pytest

from app.schemas import ChunkStrategy, RetrievalStrategy
from app.services.embedding import HashEmbeddingProvider
from app.services.llm import LLMRateLimitError
from app.services.reranker import (
    HeuristicReranker,
    LLMReranker,
    NoneReranker,
    RerankCandidate,
    RerankResult,
)
from app.services.retrieval import run_retrieval
from app.store import InMemoryStore


def candidates() -> list[RerankCandidate]:
    return [
        RerankCandidate(
            index=0,
            text="个体工商户申请材料清单",
            heading_path="三、申请材料",
            retrieval_score=0.9,
            dense_score=0.8,
            bm25_score=10.0,
        ),
        RerankCandidate(
            index=1,
            text="企业营业执照变更流程",
            heading_path="二、办理流程",
            retrieval_score=0.8,
            dense_score=0.7,
            bm25_score=4.0,
        ),
    ]


def test_none_reranker_preserves_fused_order() -> None:
    reranked = NoneReranker().rerank("申请材料", candidates(), top_k=2)
    assert [item.index for item in reranked] == [0, 1]


def test_heuristic_reranker_prefers_lexical_match() -> None:
    reranked = HeuristicReranker().rerank("申请材料", candidates(), top_k=2)
    assert reranked[0].index == 0


def test_llm_reranker_parses_and_orders_json() -> None:
    class FakeChat:
        name = "fake-chat"

        def chat(self, messages, *, temperature=0.1, max_tokens=800):
            assert temperature == 0.0
            return '[{"index": 2, "score": 0.91}, {"index": 1, "score": 0.22}]'

    reranked = LLMReranker(FakeChat()).rerank("变更流程", candidates(), top_k=2)
    assert [item.index for item in reranked] == [1, 0]
    assert reranked[0].score == pytest.approx(0.91)


class ReverseReranker:
    name = "reverse-test"

    def rerank(self, query, candidates, *, top_k):
        del query
        return [
            RerankResult(index=candidate.index, score=1.0 - candidate.index)
            for candidate in reversed(candidates)
        ][:top_k]


class FailingReranker:
    name = "failing-test"

    def rerank(self, query, candidates, *, top_k):
        raise RuntimeError("reranker offline")


@pytest.mark.asyncio
async def test_retrieval_uses_injected_reranker() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, trace = run_retrieval(
        chunks=chunks,
        query="营业执照变更办理时限",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=3,
        embedding_provider=HashEmbeddingProvider(),
        reranker_provider=ReverseReranker(),
    )
    rerank_stage = next(stage for stage in trace.stages if stage.key == "rerank")
    assert rerank_stage.detail == "reverse-test"
    assert len(run.results) == 3


@pytest.mark.asyncio
async def test_retrieval_falls_back_when_reranker_fails() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, trace = run_retrieval(
        chunks=chunks,
        query="青年人才租房补贴条件",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=3,
        embedding_provider=HashEmbeddingProvider(),
        reranker_provider=FailingReranker(),
    )
    rerank_stage = next(stage for stage in trace.stages if stage.key == "rerank")
    assert "降级" in rerank_stage.detail
    assert "RuntimeError" in rerank_stage.detail
    assert len(run.results) == 3


def test_llm_reranker_retries_rate_limit(monkeypatch) -> None:
    class RateLimitedChat:
        name = "rate-limited-chat"

        def __init__(self) -> None:
            self.calls = 0

        def chat(self, messages, *, temperature=0.1, max_tokens=800):
            self.calls += 1
            if self.calls == 1:
                raise LLMRateLimitError("limited", retry_after_seconds=0)
            return '[{"index": 1, "score": 1.0}, {"index": 2, "score": 0.5}]'

    sleeps: list[float] = []
    monkeypatch.setattr("app.services.reranker.time.sleep", sleeps.append)
    chat = RateLimitedChat()
    reranked = LLMReranker(chat).rerank("申请材料", candidates(), top_k=2)

    assert chat.calls == 2
    assert sleeps
    assert reranked[0].index == 0
