import pytest

from app.config import get_settings
from app.schemas import ChunkStrategy
from app.services.embedding import HashEmbeddingProvider
from app.services.evaluation_dataset import get_evaluation_dataset
from app.store import InMemoryStore


@pytest.mark.asyncio
async def test_synthetic_dataset_has_reproducible_dev_test_split() -> None:
    all_cases = get_evaluation_dataset("policy-synthetic-v1", "all").cases
    dev_cases = get_evaluation_dataset("policy-synthetic-v1", "dev").cases
    test_cases = get_evaluation_dataset("policy-synthetic-v1", "test").cases

    assert len(all_cases) == 152
    assert len(dev_cases) == 114
    assert len(test_cases) == 38
    assert len({case.id for case in all_cases}) == 152
    assert len({case.query for case in all_cases}) == 152
    assert {case.id for case in dev_cases}.isdisjoint({case.id for case in test_cases})


@pytest.mark.asyncio
async def test_synthetic_labels_point_to_real_chunks() -> None:
    store = InMemoryStore(
        HashEmbeddingProvider(dimensions=get_settings().hash_embedding_dimensions)
    )
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    labels = {(chunk.document_id, chunk.heading_path) for chunk in chunks}
    cases = get_evaluation_dataset("policy-synthetic-v1", "all").cases

    missing = [
        case.id
        for case in cases
        if (case.expected_document_id, case.expected_heading) not in labels
    ]
    assert missing == []


def test_unknown_dataset_and_split_are_rejected() -> None:
    with pytest.raises(ValueError):
        get_evaluation_dataset("unknown", "test")
    with pytest.raises(ValueError):
        get_evaluation_dataset("policy-synthetic-v1", "holdout")
