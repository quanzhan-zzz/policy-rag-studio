from uuid import uuid4

import pytest

from app.schemas import ChunkStrategy, IndexTaskStatus
from app.services.embedding import HashEmbeddingProvider
from app.services.indexing import execute_index_task
from app.store import InMemoryStore


@pytest.mark.asyncio
async def test_execute_index_task_reaches_ready_and_is_idempotent() -> None:
    store = InMemoryStore()
    document, task = await store.create_upload_task(
        f"index-{uuid4().hex[:8]}.md",
        "# 异步测试政策\n\n一、适用范围\n用于异步索引测试。".encode(),
        title="异步测试政策",
    )

    completed = await execute_index_task(store, task.id)
    assert completed is not None
    assert completed.status is IndexTaskStatus.READY
    assert len(await store.list_chunks(document.id, ChunkStrategy.HEADING)) > 0

    repeated = await execute_index_task(store, task.id)
    assert repeated is not None
    assert repeated.id == task.id
    assert repeated.status is IndexTaskStatus.READY
    assert repeated.attempts == 1


@pytest.mark.asyncio
async def test_execute_index_task_marks_parse_failure() -> None:
    store = InMemoryStore()
    document, task = await store.create_upload_task(
        f"broken-{uuid4().hex[:8]}.pdf",
        b"not-a-real-pdf",
        title="损坏 PDF",
    )

    failed = await execute_index_task(
        store,
        task.id,
        embedding_provider=HashEmbeddingProvider(dimensions=192),
    )
    assert failed is not None
    assert failed.status is IndexTaskStatus.FAILED
    assert failed.error_code == "invalid_document"
    current = await store.get_document(document.id)
    assert current is not None
    assert current.status == IndexTaskStatus.FAILED.value
    assert current.index_error


class FlakyEmbeddingProvider(HashEmbeddingProvider):
    name = "flaky-embedding"

    def __init__(self) -> None:
        super().__init__(dimensions=192)
        self.fail_once = True

    def embed_documents(self, texts):
        if self.fail_once:
            self.fail_once = False
            raise TimeoutError("temporary outage")
        return super().embed_documents(texts)


@pytest.mark.asyncio
async def test_failed_index_task_can_be_retried_successfully() -> None:
    store = InMemoryStore()
    document, task = await store.create_upload_task(
        f"retry-{uuid4().hex[:8]}.md",
        "# 重试测试\n\n一、适用范围\n用于验证失败重试。".encode(),
        title="重试测试",
    )
    flaky = FlakyEmbeddingProvider()

    failed = await execute_index_task(store, task.id, embedding_provider=flaky)
    assert failed is not None
    assert failed.status is IndexTaskStatus.FAILED
    assert failed.error_code == "embedding_unavailable"

    retried = await store.retry_index_task(task.id)
    assert retried is not None
    assert retried.status is IndexTaskStatus.QUEUED

    completed = await execute_index_task(
        store,
        task.id,
        embedding_provider=HashEmbeddingProvider(dimensions=192),
    )
    assert completed is not None
    assert completed.status is IndexTaskStatus.READY
    assert completed.attempts == 2
    current = await store.get_document(document.id)
    assert current is not None
    assert current.status == "ready"


@pytest.mark.asyncio
async def test_cancel_requested_processing_task_is_cancelled() -> None:
    store = InMemoryStore()
    _, task = await store.create_upload_task(
        f"cancel-{uuid4().hex[:8]}.md",
        b"# cancel\n\ncontent",
        title="Cancel test",
    )
    await store.claim_index_task(task.id)
    requested = await store.request_cancel_index_task(task.id)
    assert requested is not None
    assert requested.cancel_requested

    cancelled = await execute_index_task(store, task.id)
    assert cancelled is not None
    assert cancelled.status is IndexTaskStatus.CANCELLED
