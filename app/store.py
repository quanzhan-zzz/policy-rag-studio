from datetime import UTC, datetime
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.config import get_settings
from app.schemas import (
    ChunkRecord,
    ChunkStrategy,
    DocumentSummary,
    EvaluationSummary,
    TraceRecord,
)
from app.services.chunking import chunk_document
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.parsing import parse_document
from app.services.seed import SEED_DOCUMENTS
from app.services.text import tokenize


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

    async def record_trace(self, trace: TraceRecord) -> None: ...

    async def get_trace(self, trace_id: str) -> TraceRecord | None: ...

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
            status="indexed",
            effective_date=effective_date,
            chunk_count=len(chunks_by_strategy[ChunkStrategy.HEADING]),
            updated_at=now,
            tags=tags,
        )
        self.documents[document_id] = document
        self.document_text[document_id] = text
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

    async def record_trace(self, trace: TraceRecord) -> None:
        with self.lock:
            self.traces[trace.id] = trace

    async def get_trace(self, trace_id: str) -> TraceRecord | None:
        with self.lock:
            return self.traces.get(trace_id)

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
