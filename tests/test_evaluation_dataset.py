import hashlib
import json
from pathlib import Path

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


@pytest.mark.asyncio
async def test_official_dataset_is_frozen_and_labeled() -> None:
    all_cases = get_evaluation_dataset("policy-official-v1", "all").cases
    dev_cases = get_evaluation_dataset("policy-official-v1", "dev").cases
    test_cases = get_evaluation_dataset("policy-official-v1", "test").cases

    assert len(all_cases) == 40
    assert len(dev_cases) == 20
    assert len(test_cases) == 20
    assert len({case.id for case in all_cases}) == 40
    assert len({case.query for case in all_cases}) == 40
    assert {case.id for case in dev_cases}.isdisjoint({case.id for case in test_cases})
    assert all(case.gold_evidence for case in all_cases)
    assert all(case.query.strip() != case.expected_heading for case in all_cases)


@pytest.mark.asyncio
async def test_official_labels_point_to_real_chunks() -> None:
    store = InMemoryStore(
        HashEmbeddingProvider(dimensions=get_settings().hash_embedding_dimensions),
        seed_demo_data=False,
        seed_official_data=True,
    )
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    labels = {(chunk.document_id, chunk.heading_path) for chunk in chunks}
    cases = get_evaluation_dataset("policy-official-v1", "all").cases

    missing = [
        case.id
        for case in cases
        if (case.expected_document_id, case.expected_heading) not in labels
    ]
    assert missing == []


def test_official_dataset_checksum_is_frozen() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "eval"
        / "policy-official-v1.manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_path = manifest_path.parent / "policy-official-v1.jsonl"

    assert hashlib.sha256(dataset_path.read_bytes()).hexdigest() == manifest["sha256"]
    assert manifest["case_count"] == 40
    assert manifest["dev_count"] == 20
    assert manifest["test_count"] == 20
