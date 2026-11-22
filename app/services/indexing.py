import asyncio
import logging

import httpx

from app.config import get_settings
from app.schemas import ChunkRecord, ChunkStrategy, IndexTask, IndexTaskStatus
from app.services.chunking import chunk_document
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.parsing import UnsupportedDocumentError, parse_document
from app.store import Store

logger = logging.getLogger(__name__)


def _classify_error(error: Exception) -> tuple[str, str]:
    if isinstance(error, UnsupportedDocumentError):
        return "unsupported_document", "不支持的文件类型"
    if isinstance(error, ValueError):
        return "invalid_document", str(error)[:1_000] or "文档内容无效"
    if isinstance(error, (httpx.HTTPError, TimeoutError)):
        return "embedding_unavailable", "Embedding 服务暂时不可用"
    return "indexing_failed", f"索引失败：{type(error).__name__}"


async def _cancel_if_requested(store: Store, task_id: str) -> IndexTask | None:
    current = await store.get_index_task(task_id)
    if current is None or not current.cancel_requested:
        return None
    if current.status not in {
        IndexTaskStatus.PARSING,
        IndexTaskStatus.CHUNKING,
        IndexTaskStatus.EMBEDDING,
    }:
        return None
    return await store.transition_index_task(
        task_id,
        IndexTaskStatus.CANCELLED,
        current.progress,
    )


async def execute_index_task(
    store: Store,
    task_id: str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    stale_after_seconds: int = 120,
) -> IndexTask | None:
    task = await store.claim_index_task(task_id, stale_after_seconds=stale_after_seconds)
    if task is None:
        return await store.get_index_task(task_id)

    provider = embedding_provider or get_embedding_provider()
    try:
        source = await store.get_document_source(task.document_id)
        if source is None:
            raise ValueError("文档不存在")
        content_text = source.content_text
        if not content_text:
            try:
                content_text = await asyncio.to_thread(
                    parse_document,
                    source.document.file_name,
                    source.source_content,
                )
            except UnsupportedDocumentError:
                raise
            except Exception as error:
                raise ValueError("文档解析失败") from error
        if not content_text.strip():
            raise ValueError("文档解析结果为空")
        cancelled = await _cancel_if_requested(store, task.id)
        if cancelled is not None:
            return cancelled

        await store.transition_index_task(task.id, IndexTaskStatus.CHUNKING, 35)
        chunks: list[ChunkRecord] = []
        for strategy in ChunkStrategy:
            chunks.extend(
                await asyncio.to_thread(
                    chunk_document,
                    content_text,
                    source.document.id,
                    source.document.title,
                    strategy,
                )
            )

        cancelled = await _cancel_if_requested(store, task.id)
        if cancelled is not None:
            return cancelled

        await store.transition_index_task(task.id, IndexTaskStatus.EMBEDDING, 65)
        vectors = await asyncio.to_thread(
            provider.embed_documents,
            [chunk.text for chunk in chunks],
        )
        expected = get_settings().embedding_dimensions
        if len(vectors) != len(chunks):
            raise ValueError("Embedding 返回数量与 Chunk 数量不一致")
        if any(len(vector) != expected for vector in vectors):
            raise ValueError(f"Embedding 维度必须为 {expected}")
        cancelled = await _cancel_if_requested(store, task.id)
        if cancelled is not None:
            return cancelled

        await store.apply_document_index(
            source.document.id,
            content_text,
            chunks,
            {chunk.id: vector for chunk, vector in zip(chunks, vectors, strict=True)},
        )
        return await store.transition_index_task(task.id, IndexTaskStatus.READY, 100)
    except Exception as error:
        logger.exception("Index task %s failed", task_id)
        error_code, error_message = _classify_error(error)
        current = await store.get_index_task(task_id)
        return await store.transition_index_task(
            task_id,
            IndexTaskStatus.FAILED,
            current.progress if current else 0,
            error_code=error_code,
            error_message=error_message,
        )
