from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.config import get_settings
from app.schemas import (
    ChunkRecord,
    ChunkStrategy,
    DocumentSummary,
    EvaluationSummary,
    IndexTask,
    IndexTaskKind,
    IndexTaskStatus,
    TraceRecord,
    TraceStage,
)
from app.services.chunking import chunk_document
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.parsing import parse_document
from app.services.seed import SEED_DOCUMENTS
from app.services.text import tokenize


@dataclass(frozen=True, slots=True)
class DocumentSource:
    document: DocumentSummary
    source_content: bytes
    content_text: str | None


PROCESSING_TASK_STATUSES = {
    IndexTaskStatus.PARSING,
    IndexTaskStatus.CHUNKING,
    IndexTaskStatus.EMBEDDING,
}
ALLOWED_TASK_TRANSITIONS: dict[IndexTaskStatus, set[IndexTaskStatus]] = {
    IndexTaskStatus.QUEUED: {
        IndexTaskStatus.PARSING,
        IndexTaskStatus.FAILED,
        IndexTaskStatus.CANCELLED,
    },
    IndexTaskStatus.PARSING: {
        IndexTaskStatus.CHUNKING,
        IndexTaskStatus.FAILED,
        IndexTaskStatus.CANCELLED,
    },
    IndexTaskStatus.CHUNKING: {
        IndexTaskStatus.EMBEDDING,
        IndexTaskStatus.FAILED,
        IndexTaskStatus.CANCELLED,
    },
    IndexTaskStatus.EMBEDDING: {
        IndexTaskStatus.READY,
        IndexTaskStatus.FAILED,
        IndexTaskStatus.CANCELLED,
    },
    IndexTaskStatus.FAILED: set(),
    IndexTaskStatus.READY: set(),
    IndexTaskStatus.CANCELLED: set(),
}


class Store(Protocol):
    backend: str

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...

    async def list_documents(self) -> list[DocumentSummary]: ...

    async def get_document(self, document_id: str) -> DocumentSummary | None: ...

    async def list_chunks(
        self,
        document_id: str,
        strategy: ChunkStrategy,
    ) -> list[ChunkRecord]: ...

    async def all_chunks(self, strategy: ChunkStrategy) -> list[ChunkRecord]: ...

    async def dense_scores(
        self,
        strategy: ChunkStrategy,
        query_vector: list[float],
        limit: int = 64,
    ) -> list[tuple[str, float]]: ...

    async def update_chunk(self, chunk_id: str, text: str) -> ChunkRecord | None: ...

    async def add_upload(
        self,
        file_name: str,
        content: bytes,
        title: str | None = None,
        department: str = "用户上传",
    ) -> DocumentSummary: ...

    async def reindex_document(self, document_id: str) -> DocumentSummary | None: ...

    async def create_upload_task(
        self,
        file_name: str,
        content: bytes,
        title: str | None = None,
        department: str = "用户上传",
    ) -> tuple[DocumentSummary, IndexTask]: ...

    async def create_reindex_task(self, document_id: str) -> IndexTask | None: ...

    async def get_index_task(self, task_id: str) -> IndexTask | None: ...

    async def claim_index_task(
        self,
        task_id: str,
        stale_after_seconds: int = 120,
    ) -> IndexTask | None: ...

    async def transition_index_task(
        self,
        task_id: str,
        status: IndexTaskStatus,
        progress: int,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> IndexTask | None: ...

    async def retry_index_task(self, task_id: str) -> IndexTask | None: ...

    async def request_cancel_index_task(self, task_id: str) -> IndexTask | None: ...

    async def list_stale_index_tasks(self, stale_after_seconds: int) -> list[IndexTask]: ...

    async def get_document_source(self, document_id: str) -> DocumentSource | None: ...

    async def apply_document_index(
        self,
        document_id: str,
        content_text: str,
        chunks: list[ChunkRecord],
        vectors: dict[str, list[float]],
    ) -> DocumentSummary | None: ...

    async def record_trace(self, trace: TraceRecord) -> None: ...

    async def get_trace(self, trace_id: str) -> TraceRecord | None: ...

    async def complete_trace_generation(
        self,
        trace_id: str,
        stage: TraceStage,
        total_ms: float,
    ) -> None: ...

    async def record_evaluation(self, evaluation: EvaluationSummary) -> EvaluationSummary: ...

    async def get_latest_evaluation(self) -> EvaluationSummary | None: ...

    async def count_chunks(self) -> int: ...

    async def count_retrieval_runs(self) -> int: ...


class InMemoryStore:
    """Repository adapter used by tests and the no-database demo mode."""

    backend = "memory"

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.lock = RLock()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.documents: dict[str, DocumentSummary] = {}
        self.document_text: dict[str, str] = {}
        self.document_source: dict[str, bytes] = {}
        self.index_tasks: dict[str, IndexTask] = {}
        self._reindex_keys: dict[str, str] = {}
        self.chunks: dict[tuple[str, ChunkStrategy], list[ChunkRecord]] = {}
        self.chunk_index: dict[str, ChunkRecord] = {}
        self.chunk_vectors: dict[str, list[float]] = {}
        self.traces: dict[str, TraceRecord] = {}
        self.evaluations: dict[str, EvaluationSummary] = {}
        self._seed()

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def _seed(self) -> None:
        for seed in SEED_DOCUMENTS:
            self._create_document(
                document_id=seed.id,
                title=seed.title,
                department=seed.department,
                file_name=f"{seed.id}.md",
                effective_date=seed.effective_date,
                tags=list(seed.tags),
                text=seed.text,
            )

    def _create_document(
        self,
        document_id: str,
        title: str,
        department: str,
        file_name: str,
        effective_date: str,
        tags: list[str],
        text: str,
    ) -> DocumentSummary:
        now = datetime.now(UTC)
        chunks_by_strategy: dict[ChunkStrategy, list[ChunkRecord]] = {}
        for strategy in ChunkStrategy:
            chunks = chunk_document(text, document_id, title, strategy)
            chunks_by_strategy[strategy] = chunks
            self.chunks[(document_id, strategy)] = chunks
            self.chunk_index.update({chunk.id: chunk for chunk in chunks})
            self._remember_vectors(chunks)
        document = DocumentSummary(
            id=document_id,
            title=title,
            department=department,
            file_name=file_name,
            status="ready",
            effective_date=effective_date,
            chunk_count=len(chunks_by_strategy[ChunkStrategy.HEADING]),
            updated_at=now,
            tags=tags,
            index_progress=100,
        )
        self.documents[document_id] = document
        self.document_text[document_id] = text
        self.document_source[document_id] = text.encode()
        return document

    async def list_documents(self) -> list[DocumentSummary]:
        with self.lock:
            return sorted(
                self.documents.values(),
                key=lambda document: document.updated_at,
                reverse=True,
            )

    async def get_document(self, document_id: str) -> DocumentSummary | None:
        with self.lock:
            return self.documents.get(document_id)

    async def list_chunks(self, document_id: str, strategy: ChunkStrategy) -> list[ChunkRecord]:
        with self.lock:
            return list(self.chunks.get((document_id, strategy), []))

    async def all_chunks(self, strategy: ChunkStrategy) -> list[ChunkRecord]:
        with self.lock:
            result: list[ChunkRecord] = []
            for document in self.documents.values():
                result.extend(self.chunks.get((document.id, strategy), []))
            return result

    async def dense_scores(
        self,
        strategy: ChunkStrategy,
        query_vector: list[float],
        limit: int = 64,
    ) -> list[tuple[str, float]]:
        with self.lock:
            chunks = [
                chunk
                for document in self.documents.values()
                for chunk in self.chunks.get((document.id, strategy), [])
            ]
            scores = [
                (chunk.id, self._cosine(query_vector, self.chunk_vectors[chunk.id]))
                for chunk in chunks
                if chunk.id in self.chunk_vectors
            ]
            return sorted(scores, key=lambda item: item[1], reverse=True)[:limit]

    async def update_chunk(self, chunk_id: str, text: str) -> ChunkRecord | None:
        with self.lock:
            original = self.chunk_index.get(chunk_id)
            if original is None:
                return None
            updated = original.model_copy(
                update={
                    "text": text,
                    "tokens": len(tokenize(text)),
                }
            )
            self.chunk_index[chunk_id] = updated
            self._remember_vectors([updated])
            key = (original.document_id, original.strategy)
            self.chunks[key] = [
                updated if chunk.id == chunk_id else chunk for chunk in self.chunks.get(key, [])
            ]
            document = self.documents.get(original.document_id)
            if document:
                self.documents[original.document_id] = document.model_copy(
                    update={"updated_at": datetime.now(UTC)}
                )
            return updated

    async def add_upload(
        self,
        file_name: str,
        content: bytes,
        title: str | None = None,
        department: str = "用户上传",
    ) -> DocumentSummary:
        text = parse_document(file_name, content)
        if not text.strip():
            raise ValueError("文档解析结果为空")
        document_id = f"upload-{uuid4().hex[:8]}"
        with self.lock:
            return self._create_document(
                document_id=document_id,
                title=title or file_name.rsplit(".", 1)[0],
                department=department,
                file_name=file_name,
                effective_date=datetime.now(UTC).date().isoformat(),
                tags=["上传", "演示"],
                text=text,
            )

    async def reindex_document(self, document_id: str) -> DocumentSummary | None:
        with self.lock:
            document = self.documents.get(document_id)
            text = self.document_text.get(document_id)
            if document is None or text is None:
                return document
            for strategy in ChunkStrategy:
                key = (document_id, strategy)
                for chunk in self.chunks.get(key, []):
                    self.chunk_index.pop(chunk.id, None)
                    self.chunk_vectors.pop(chunk.id, None)
                chunks = chunk_document(text, document_id, document.title, strategy)
                self.chunks[key] = chunks
                self.chunk_index.update({chunk.id: chunk for chunk in chunks})
                self._remember_vectors(chunks)
            updated = document.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "chunk_count": len(self.chunks[(document_id, ChunkStrategy.HEADING)]),
                }
            )
            self.documents[document_id] = updated
            return updated

    async def create_upload_task(
        self,
        file_name: str,
        content: bytes,
        title: str | None = None,
        department: str = "用户上传",
    ) -> tuple[DocumentSummary, IndexTask]:
        if not content:
            raise ValueError("上传文件为空")
        now = datetime.now(UTC)
        document_id = f"upload-{uuid4().hex[:8]}"
        task_id = f"idx_{uuid4().hex[:12]}"
        task = IndexTask(
            id=task_id,
            document_id=document_id,
            kind=IndexTaskKind.INGEST,
            status=IndexTaskStatus.QUEUED,
            progress=0,
            attempts=0,
            created_at=now,
            updated_at=now,
        )
        document = DocumentSummary(
            id=document_id,
            title=title or file_name.rsplit(".", 1)[0],
            department=department,
            file_name=file_name,
            status=IndexTaskStatus.QUEUED.value,
            effective_date=now.date().isoformat(),
            chunk_count=0,
            updated_at=now,
            tags=["上传", "异步索引"],
            index_task_id=task_id,
            index_progress=0,
        )
        with self.lock:
            self.documents[document_id] = document
            self.document_source[document_id] = content
            self.index_tasks[task_id] = task
            for strategy in ChunkStrategy:
                self.chunks[(document_id, strategy)] = []
        return document, task

    async def create_reindex_task(self, document_id: str) -> IndexTask | None:
        with self.lock:
            document = self.documents.get(document_id)
            if document is None:
                return None
            source = self.document_source.get(document_id, b"")
            if not source and document_id in self.document_text:
                source = self.document_text[document_id].encode()
            digest = sha256(source).hexdigest()[:16]
            idempotency_key = f"reindex:{document_id}:{digest}"
            existing_id = self._reindex_keys.get(idempotency_key)
            existing = self.index_tasks.get(existing_id) if existing_id else None
            if existing is not None:
                return existing
            now = datetime.now(UTC)
            task = IndexTask(
                id=f"idx_{uuid4().hex[:12]}",
                document_id=document_id,
                kind=IndexTaskKind.REINDEX,
                status=IndexTaskStatus.QUEUED,
                progress=0,
                attempts=0,
                created_at=now,
                updated_at=now,
            )
            # Idempotency keys are internal to the adapter; IndexTask exposes the public contract.
            task_key = idempotency_key
            self.index_tasks[task.id] = task
            self._reindex_keys[task_key] = task.id
            self.documents[document_id] = document.model_copy(
                update={
                    "status": IndexTaskStatus.QUEUED.value,
                    "index_task_id": task.id,
                    "index_progress": 0,
                    "index_error": None,
                    "updated_at": now,
                }
            )
            return task

    async def get_index_task(self, task_id: str) -> IndexTask | None:
        with self.lock:
            return self.index_tasks.get(task_id)

    async def claim_index_task(
        self,
        task_id: str,
        stale_after_seconds: int = 120,
    ) -> IndexTask | None:
        with self.lock:
            task = self.index_tasks.get(task_id)
            if task is None:
                return None
            if task.cancel_requested:
                now = datetime.now(UTC)
                cancelled = task.model_copy(
                    update={
                        "status": IndexTaskStatus.CANCELLED,
                        "updated_at": now,
                        "finished_at": now,
                    }
                )
                self.index_tasks[task_id] = cancelled
                self._sync_document_task(cancelled)
                return None
            stale_before = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
            claimable = task.status is IndexTaskStatus.QUEUED or (
                task.status in PROCESSING_TASK_STATUSES and task.updated_at < stale_before
            )
            if not claimable:
                return None
            now = datetime.now(UTC)
            claimed = task.model_copy(
                update={
                    "status": IndexTaskStatus.PARSING,
                    "progress": 10,
                    "attempts": task.attempts + 1,
                    "started_at": task.started_at or now,
                    "updated_at": now,
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.index_tasks[task_id] = claimed
            self._sync_document_task(claimed)
            return claimed

    async def transition_index_task(
        self,
        task_id: str,
        status: IndexTaskStatus,
        progress: int,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> IndexTask | None:
        with self.lock:
            task = self.index_tasks.get(task_id)
            if task is None:
                return None
            if status not in ALLOWED_TASK_TRANSITIONS[task.status]:
                raise ValueError(f"非法索引状态转换：{task.status} → {status}")
            now = datetime.now(UTC)
            terminal = status in {
                IndexTaskStatus.READY,
                IndexTaskStatus.FAILED,
                IndexTaskStatus.CANCELLED,
            }
            updated = task.model_copy(
                update={
                    "status": status,
                    "progress": 100 if status is IndexTaskStatus.READY else progress,
                    "error_code": error_code,
                    "error_message": error_message,
                    "updated_at": now,
                    "finished_at": now if terminal else None,
                }
            )
            self.index_tasks[task_id] = updated
            self._sync_document_task(updated)
            return updated

    async def retry_index_task(self, task_id: str) -> IndexTask | None:
        with self.lock:
            task = self.index_tasks.get(task_id)
            if task is None or task.status not in {
                IndexTaskStatus.FAILED,
                IndexTaskStatus.CANCELLED,
            }:
                return None
            now = datetime.now(UTC)
            retried = task.model_copy(
                update={
                    "status": IndexTaskStatus.QUEUED,
                    "progress": 0,
                    "error_code": None,
                    "error_message": None,
                    "updated_at": now,
                    "started_at": None,
                    "finished_at": None,
                    "cancel_requested": False,
                }
            )
            self.index_tasks[task_id] = retried
            self._sync_document_task(retried)
            return retried

    async def request_cancel_index_task(self, task_id: str) -> IndexTask | None:
        with self.lock:
            task = self.index_tasks.get(task_id)
            if task is None:
                return None
            if task.status in {
                IndexTaskStatus.READY,
                IndexTaskStatus.FAILED,
                IndexTaskStatus.CANCELLED,
            }:
                return task
            if task.status is IndexTaskStatus.QUEUED:
                now = datetime.now(UTC)
                cancelled = task.model_copy(
                    update={
                        "status": IndexTaskStatus.CANCELLED,
                        "updated_at": now,
                        "finished_at": now,
                    }
                )
                self.index_tasks[task_id] = cancelled
                self._sync_document_task(cancelled)
                return cancelled
            updated = task.model_copy(
                update={"cancel_requested": True, "updated_at": datetime.now(UTC)}
            )
            self.index_tasks[task_id] = updated
            return updated

    async def list_stale_index_tasks(self, stale_after_seconds: int) -> list[IndexTask]:
        stale_before = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        with self.lock:
            return [
                task
                for task in self.index_tasks.values()
                if task.status in PROCESSING_TASK_STATUSES and task.updated_at < stale_before
            ]

    async def get_document_source(self, document_id: str) -> DocumentSource | None:
        with self.lock:
            document = self.documents.get(document_id)
            if document is None:
                return None
            return DocumentSource(
                document=document,
                source_content=self.document_source.get(document_id, b""),
                content_text=self.document_text.get(document_id),
            )

    async def apply_document_index(
        self,
        document_id: str,
        content_text: str,
        chunks: list[ChunkRecord],
        vectors: dict[str, list[float]],
    ) -> DocumentSummary | None:
        with self.lock:
            document = self.documents.get(document_id)
            if document is None:
                return None
            for strategy in ChunkStrategy:
                key = (document_id, strategy)
                for chunk in self.chunks.get(key, []):
                    self.chunk_index.pop(chunk.id, None)
                    self.chunk_vectors.pop(chunk.id, None)
                strategy_chunks = [chunk for chunk in chunks if chunk.strategy is strategy]
                self.chunks[key] = strategy_chunks
                self.chunk_index.update({chunk.id: chunk for chunk in strategy_chunks})
            self.chunk_vectors.update(vectors)
            self.document_text[document_id] = content_text
            heading_count = len(
                [chunk for chunk in chunks if chunk.strategy is ChunkStrategy.HEADING]
            )
            updated = document.model_copy(
                update={
                    "chunk_count": heading_count,
                    "updated_at": datetime.now(UTC),
                }
            )
            self.documents[document_id] = updated
            return updated

    def _sync_document_task(self, task: IndexTask) -> None:
        document = self.documents.get(task.document_id)
        if document is None:
            return
        self.documents[task.document_id] = document.model_copy(
            update={
                "status": task.status.value,
                "index_task_id": task.id,
                "index_progress": task.progress,
                "index_error": task.error_message,
                "updated_at": task.updated_at,
            }
        )

    async def record_trace(self, trace: TraceRecord) -> None:
        with self.lock:
            self.traces[trace.id] = trace

    async def get_trace(self, trace_id: str) -> TraceRecord | None:
        with self.lock:
            return self.traces.get(trace_id)

    async def complete_trace_generation(
        self,
        trace_id: str,
        stage: TraceStage,
        total_ms: float,
    ) -> None:
        with self.lock:
            trace = self.traces.get(trace_id)
            if trace is None:
                return
            self.traces[trace_id] = trace.model_copy(
                update={
                    "stages": [*trace.stages, stage],
                    "total_ms": round(total_ms, 3),
                }
            )

    async def record_evaluation(self, evaluation: EvaluationSummary) -> EvaluationSummary:
        stored = evaluation.model_copy(update={"id": evaluation.id or f"eval_{uuid4().hex[:12]}"})
        with self.lock:
            self.evaluations[stored.id or ""] = stored
        return stored

    async def get_latest_evaluation(self) -> EvaluationSummary | None:
        with self.lock:
            if not self.evaluations:
                return None
            return max(self.evaluations.values(), key=lambda item: item.generated_at)

    async def count_chunks(self) -> int:
        with self.lock:
            return len(self.chunk_index)

    async def count_retrieval_runs(self) -> int:
        with self.lock:
            return len(self.traces)

    def _remember_vectors(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        vectors = self.embedding_provider.embed_documents([chunk.text for chunk in chunks])
        expected = get_settings().embedding_dimensions
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != expected:
                raise ValueError(
                    f"Embedding 维度不匹配：期望 {expected}，实际 {len(vector)}"
                )
            self.chunk_vectors[chunk.id] = vector

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))
