import pytest

from app.services.evaluation import evaluate_store
from app.services.reranker import RerankResult
from app.store import InMemoryStore


class IdentityReranker:
    name = "identity-test"

    def rerank(self, query, candidates, *, top_k):
        del query
        return [
            RerankResult(index=candidate.index, score=candidate.retrieval_score)
            for candidate in candidates[:top_k]
        ]


@pytest.mark.asyncio
async def test_evaluation_records_active_reranker() -> None:
    summary = await evaluate_store(
        InMemoryStore(),
        reranker_provider=IdentityReranker(),
    )
    assert summary.reranker_provider == "identity-test"
    assert summary.case_count == 10
    assert len(summary.rows) == 4
