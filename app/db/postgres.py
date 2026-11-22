import asyncio
import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.db.base import Base
from app.db.models import (
    ChunkRow,
    DocumentRow,
    EmbeddingRow,
    EvaluationRunRow,
    IndexTaskRow,
    TraceRow,
)
from app.schemas import (
    ChunkRecord,
    ChunkStrategy,
    DocumentSummary,
    EvaluationSummary,
    FailureBucket,
    IndexTask,
    IndexTaskKind,
    IndexTaskStatus,
    MetricRow,
    TraceRecord,
    TraceStage,
)
from app.services.chunking import chunk_document
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.parsing import parse_document
from app.services.seed import SEED_DOCUMENTS
from app.services.text import tokenize
from app.store import (
    ALLOWED_TASK_TRANSITIONS,
    PROCESSING_TASK_STATUSES,
    DocumentSource,
)

logger = logging.getLogger(__name__)


class PostgresStore:
    """PostgreSQL repository adapter for documents, chunks, and traces."""

    backend = "postgres"

    def __init__(
        self,
        engine: AsyncEngine,
        sessions: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.engine = engine
        self.sessions = sessions
        self.embedding_provider = embedding_provider

    @classmethod
    async def create(
        cls,
        database_url: str,
        *,
        seed_demo_data: bool = True,
        embedding_provider: EmbeddingProvider | None = None,
        initialize_schema: bool = False,
    ) -> "PostgresStore":
        engine = create_async_engine(database_url, pool_pre_ping=True)
        store = cls(
            engine,
            async_sessionmaker(engine, expire_on_commit=False),
            embedding_provider or get_embedding_provider(),
        )
        await store.initialize(
            seed_demo_data=seed_demo_data,
            initialize_schema=initialize_schema,
        )
        return store

    async def initialize(
        self,
        *,
        seed_demo_data: bool,
        initialize_schema: bool,
    ) -> None:
        if initialize_schema:
            async with self.engine.begin() as connection:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await connection.run_sync(Base.metadata.create_all)
        if seed_demo_data:
            await self._seed()
            await self._backfill_embeddings()

    async def _backfill_embeddings(self) -> None:
        async with self.sessions() as session:
            await session.execute(
                delete(EmbeddingRow).where(
                    EmbeddingRow.model_name != self.embedding_provider.name
                )
            )
            chunk_rows = (
                await session.scalars(
                    select(ChunkRow)
                    .outerjoin(EmbeddingRow, EmbeddingRow.chunk_id == ChunkRow.id)
                    .where(EmbeddingRow.chunk_id.is_(None))
                    .order_by(ChunkRow.document_id, ChunkRow.strategy, ChunkRow.position)
                )
            ).all()
            await session.commit()
        if not chunk_rows:
            return
        chunks = [self._to_chunk(row) for row in chunk_rows]
        try:
            embedding_rows = await self._new_embedding_rows(chunks)
        except Exception:
            logger.exception("Embedding backfill failed; retrieval will fall back to live vectors")
            return
        async with self.sessions() as session:
            session.add_all(embedding_rows)
            await session.commit()

    async def ping(self) -> bool:
        try:
            async with self.sessions() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.engine.dispose()

    async def _seed(self) -> None:
        existing_ids = {document.id for document in await self.list_documents()}
        for seed in SEED_DOCUMENTS:
            if seed.id in existing_ids:
                continue
            await self._create_document(
                document_id=seed.id,
                title=seed.title,
                department=seed.department,
                file_name=f"{seed.id}.md",
                effective_date=seed.effective_date,
                tags=list(seed.tags),
                content_text=seed.text,
            )

    async def _create_document(
        self,
        *,
        document_id: str,
        title: str,
        department: str,
        file_name: str,
        effective_date: str,
        tags: list[str],
        content_text: str,
    ) -> DocumentSummary:
        now = datetime.now(UTC)
        document = DocumentRow(
            id=document_id,
            title=title,
            department=department,
            file_name=file_name,
            status="ready",
            effective_date=effective_date,
            content_text=content_text,
            source_content=content_text.encode(),
            chunk_count=0,
            updated_at=now,
            tags=tags,
            index_progress=100,
        )
        all_chunks: list[ChunkRecord] = []
        for strategy in ChunkStrategy:
            chunks = chunk_document(content_text, document_id, title, strategy)
            if strategy is ChunkStrategy.HEADING:
                document.chunk_count = len(chunks)
            all_chunks.extend(chunks)
            document.chunks.extend(self._new_chunk_rows(chunks))
        embedding_rows = await self._new_embedding_rows(all_chunks)
        async with self.sessions() as session:
            session.add(document)
            await session.flush()
            session.add_all(embedding_rows)
            await session.commit()
        return self._to_document(document)

    async def list_documents(self) -> list[DocumentSummary]:
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(DocumentRow).order_by(DocumentRow.updated_at.desc())
                )
            ).all()
        return [self._to_document(row) for row in rows]

    async def get_document(self, document_id: str) -> DocumentSummary | None:
        async with self.sessions() as session:
            row = await session.get(DocumentRow, document_id)
        return self._to_document(row) if row else None

    async def list_chunks(
        self,
        document_id: str,
        strategy: ChunkStrategy,
    ) -> list[ChunkRecord]:
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(ChunkRow)
                    .where(
                        ChunkRow.document_id == document_id,
                        ChunkRow.strategy == strategy.value,
                    )
                    .order_by(ChunkRow.position)
                )
            ).all()
        return [self._to_chunk(row) for row in rows]

    async def all_chunks(self, strategy: ChunkStrategy) -> list[ChunkRecord]:
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(ChunkRow)
                    .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
                    .where(ChunkRow.strategy == strategy.value)
                    .order_by(DocumentRow.updated_at.desc(), ChunkRow.position)
                )
            ).all()
        return [self._to_chunk(row) for row in rows]

    async def dense_scores(
        self,
        strategy: ChunkStrategy,
        query_vector: list[float],
        limit: int = 64,
    ) -> list[tuple[str, float]]:
        distance = EmbeddingRow.embedding.cosine_distance(query_vector).label("distance")
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(ChunkRow.id, distance)
                    .join(EmbeddingRow, EmbeddingRow.chunk_id == ChunkRow.id)
                    .where(
                        ChunkRow.strategy == strategy.value,
                        EmbeddingRow.model_name == self.embedding_provider.name,
                    )
                    .order_by(distance)
                    .limit(limit)
                )
            ).all()
        return [(chunk_id, 1.0 - float(value)) for chunk_id, value in rows]

    async def update_chunk(self, chunk_id: str, text: str) -> ChunkRecord | None:
        async with self.sessions() as session:
            row = await session.get(ChunkRow, chunk_id)
            if row is None:
                return None
            row.text = text
            row.tokens = len(tokenize(text))
            document = await session.get(DocumentRow, row.document_id)
            if document is not None:
                document.updated_at = datetime.now(UTC)
            embedding = await session.get(EmbeddingRow, chunk_id)
            if embedding is None:
                embedding = EmbeddingRow(chunk_id=chunk_id)
                session.add(embedding)
            embedding.model_name = self.embedding_provider.name
            vector = await asyncio.to_thread(self.embedding_provider.embed_query, text)
            embedding.embedding = self._validated_vector(vector)
            await session.commit()
            return self._to_chunk(row)

    async def add_upload(
        self,
        file_name: str,
        content: bytes,
        title: str | None = None,
        department: str = "用户上传",
    ) -> DocumentSummary:
        content_text = parse_document(file_name, content)
        if not content_text.strip():
            raise ValueError("文档解析结果为空")
        return await self._create_document(
            document_id=f"upload-{uuid4().hex[:8]}",
            title=title or file_name.rsplit(".", 1)[0],
            department=department,
            file_name=file_name,
            effective_date=datetime.now(UTC).date().isoformat(),
            tags=["上传", "演示"],
            content_text=content_text,
        )

    async def reindex_document(self, document_id: str) -> DocumentSummary | None:
        async with self.sessions() as session:
            document = await session.get(DocumentRow, document_id)
            if document is None:
                return None
            await session.execute(delete(ChunkRow).where(ChunkRow.document_id == document_id))
            all_new_chunks: list[ChunkRow] = []
            all_chunk_records: list[ChunkRecord] = []
            for strategy in ChunkStrategy:
                chunks = chunk_document(
                    document.content_text,
                    document.id,
                    document.title,
                    strategy,
                )
                if strategy is ChunkStrategy.HEADING:
                    document.chunk_count = len(chunks)
                all_new_chunks.extend(self._new_chunk_rows(chunks))
                all_chunk_records.extend(chunks)
            session.add_all(all_new_chunks)
            await session.flush()
            session.add_all(await self._new_embedding_rows(all_chunk_records))
            document.updated_at = datetime.now(UTC)
            await session.commit()
            return self._to_document(document)

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
        document = DocumentRow(
            id=document_id,
            title=title or file_name.rsplit(".", 1)[0],
            department=department,
            file_name=file_name,
            status=IndexTaskStatus.QUEUED.value,
            effective_date=now.date().isoformat(),
            content_text=None,
            source_content=content,
            chunk_count=0,
            updated_at=now,
            tags=["上传", "异步索引"],
            index_task_id=task_id,
            index_progress=0,
            index_error=None,
        )
        task = IndexTaskRow(
            id=task_id,
            document_id=document_id,
            kind=IndexTaskKind.INGEST.value,
            status=IndexTaskStatus.QUEUED.value,
            progress=0,
            attempts=0,
            idempotency_key=f"ingest:{document_id}",
            cancel_requested=False,
            created_at=now,
            updated_at=now,
        )
        async with self.sessions() as session:
            session.add(document)
            session.add(task)
            await session.commit()
        return self._to_document(document), self._to_task(task)

    async def create_reindex_task(self, document_id: str) -> IndexTask | None:
        async with self.sessions() as session:
            document = await session.scalar(
                select(DocumentRow)
                .where(DocumentRow.id == document_id)
                .with_for_update()
            )
            if document is None:
                return None
            source = document.source_content or (document.content_text or "").encode()
            digest = sha256(source).hexdigest()[:16]
            idempotency_key = f"reindex:{document_id}:{digest}"
            existing = await session.scalar(
                select(IndexTaskRow).where(
                    IndexTaskRow.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                return self._to_task(existing)
            now = datetime.now(UTC)
            task = IndexTaskRow(
                id=f"idx_{uuid4().hex[:12]}",
                document_id=document_id,
                kind=IndexTaskKind.REINDEX.value,
                status=IndexTaskStatus.QUEUED.value,
                progress=0,
                attempts=0,
                idempotency_key=idempotency_key,
                cancel_requested=False,
                created_at=now,
                updated_at=now,
            )
            session.add(task)
            document.status = IndexTaskStatus.QUEUED.value
            document.index_task_id = task.id
            document.index_progress = 0
            document.index_error = None
            document.updated_at = now
            await session.commit()
            return self._to_task(task)

    async def get_index_task(self, task_id: str) -> IndexTask | None:
        async with self.sessions() as session:
            row = await session.get(IndexTaskRow, task_id)
        return self._to_task(row) if row else None

    async def claim_index_task(
        self,
        task_id: str,
        stale_after_seconds: int = 120,
    ) -> IndexTask | None:
        async with self.sessions() as session:
            task = await session.scalar(
                select(IndexTaskRow)
                .where(IndexTaskRow.id == task_id)
                .with_for_update()
            )
            if task is None:
                return None
            if task.cancel_requested:
                now = datetime.now(UTC)
                task.status = IndexTaskStatus.CANCELLED.value
                task.updated_at = now
                task.finished_at = now
                await self._sync_document_task(session, task)
                await session.commit()
                return None
            stale_before = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
            claimable = task.status == IndexTaskStatus.QUEUED.value or (
                task.status in {status.value for status in PROCESSING_TASK_STATUSES}
                and task.updated_at < stale_before
            )
            if not claimable:
                return None
            now = datetime.now(UTC)
            task.status = IndexTaskStatus.PARSING.value
            task.progress = 10
            task.attempts += 1
            task.started_at = task.started_at or now
            task.updated_at = now
            task.error_code = None
            task.error_message = None
            await self._sync_document_task(session, task)
            await session.commit()
            return self._to_task(task)

    async def transition_index_task(
        self,
        task_id: str,
        status: IndexTaskStatus,
        progress: int,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> IndexTask | None:
        async with self.sessions() as session:
            task = await session.scalar(
                select(IndexTaskRow)
                .where(IndexTaskRow.id == task_id)
                .with_for_update()
            )
            if task is None:
                return None
            current = IndexTaskStatus(task.status)
            if status not in ALLOWED_TASK_TRANSITIONS[current]:
                raise ValueError(f"非法索引状态转换：{current} → {status}")
            now = datetime.now(UTC)
            task.status = status.value
            task.progress = 100 if status is IndexTaskStatus.READY else progress
            task.error_code = error_code
            task.error_message = error_message
            task.updated_at = now
            if status in {
                IndexTaskStatus.READY,
                IndexTaskStatus.FAILED,
                IndexTaskStatus.CANCELLED,
            }:
                task.finished_at = now
            await self._sync_document_task(session, task)
            await session.commit()
            return self._to_task(task)

    async def retry_index_task(self, task_id: str) -> IndexTask | None:
        async with self.sessions() as session:
            task = await session.scalar(
                select(IndexTaskRow)
                .where(IndexTaskRow.id == task_id)
                .with_for_update()
            )
            if task is None or task.status not in {
                IndexTaskStatus.FAILED.value,
                IndexTaskStatus.CANCELLED.value,
            }:
                return None
            now = datetime.now(UTC)
            task.status = IndexTaskStatus.QUEUED.value
            task.progress = 0
            task.error_code = None
            task.error_message = None
            task.updated_at = now
            task.started_at = None
            task.finished_at = None
            task.cancel_requested = False
            await self._sync_document_task(session, task)
            await session.commit()
            return self._to_task(task)

    async def request_cancel_index_task(self, task_id: str) -> IndexTask | None:
        async with self.sessions() as session:
            task = await session.scalar(
                select(IndexTaskRow)
                .where(IndexTaskRow.id == task_id)
                .with_for_update()
            )
            if task is None:
                return None
            if task.status in {
                IndexTaskStatus.READY.value,
                IndexTaskStatus.FAILED.value,
                IndexTaskStatus.CANCELLED.value,
            }:
                return self._to_task(task)
            now = datetime.now(UTC)
            if task.status == IndexTaskStatus.QUEUED.value:
                task.status = IndexTaskStatus.CANCELLED.value
                task.finished_at = now
            else:
                task.cancel_requested = True
            task.updated_at = now
            await self._sync_document_task(session, task)
            await session.commit()
            return self._to_task(task)

    async def list_stale_index_tasks(self, stale_after_seconds: int) -> list[IndexTask]:
        stale_before = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        async with self.sessions() as session:
            rows = (
                await session.scalars(
                    select(IndexTaskRow)
                    .where(
                        IndexTaskRow.status.in_(
                            {status.value for status in PROCESSING_TASK_STATUSES}
                        ),
                        IndexTaskRow.updated_at < stale_before,
                    )
                    .order_by(IndexTaskRow.updated_at)
                )
            ).all()
        return [self._to_task(row) for row in rows]

    async def get_document_source(self, document_id: str) -> DocumentSource | None:
        async with self.sessions() as session:
            row = await session.get(DocumentRow, document_id)
        if row is None:
            return None
        return DocumentSource(
            document=self._to_document(row),
            source_content=row.source_content,
            content_text=row.content_text,
        )

    async def apply_document_index(
        self,
        document_id: str,
        content_text: str,
        chunks: list[ChunkRecord],
        vectors: dict[str, list[float]],
    ) -> DocumentSummary | None:
        missing = [chunk.id for chunk in chunks if chunk.id not in vectors]
        if missing:
            raise ValueError(f"缺少 Chunk 向量：{missing[0]}")
        embedding_rows = [
            EmbeddingRow(
                chunk_id=chunk.id,
                model_name=self.embedding_provider.name,
                embedding=self._validated_vector(vectors[chunk.id]),
            )
            for chunk in chunks
        ]
        async with self.sessions() as session:
            document = await session.get(DocumentRow, document_id)
            if document is None:
                return None
            await session.execute(delete(ChunkRow).where(ChunkRow.document_id == document_id))
            new_rows = self._new_chunk_rows(chunks)
            session.add_all(new_rows)
            await session.flush()
            session.add_all(embedding_rows)
            document.content_text = content_text
            document.chunk_count = len(
                [chunk for chunk in chunks if chunk.strategy is ChunkStrategy.HEADING]
            )
            document.updated_at = datetime.now(UTC)
            await session.commit()
            return self._to_document(document)

    async def record_trace(self, trace: TraceRecord) -> None:
        row = TraceRow(
            id=trace.id,
            query=trace.query,
            strategy=trace.strategy.value,
            chunk_strategy=trace.chunk_strategy.value,
            total_ms=trace.total_ms,
            created_at=trace.created_at,
            stages=[stage.model_dump(mode="json") for stage in trace.stages],
        )
        async with self.sessions() as session:
            session.add(row)
            await session.commit()

    async def get_trace(self, trace_id: str) -> TraceRecord | None:
        async with self.sessions() as session:
            row = await session.get(TraceRow, trace_id)
        if row is None:
            return None
        return TraceRecord(
            id=row.id,
            query=row.query,
            strategy=row.strategy,
            chunk_strategy=row.chunk_strategy,
            total_ms=row.total_ms,
            created_at=row.created_at,
            stages=[TraceStage.model_validate(stage) for stage in row.stages],
        )

    async def record_evaluation(self, evaluation: EvaluationSummary) -> EvaluationSummary:
        stored = evaluation.model_copy(
            update={"id": evaluation.id or f"eval_{uuid4().hex[:12]}"}
        )
        row = EvaluationRunRow(
            id=stored.id or "",
            dataset_name=stored.dataset_name,
            case_count=stored.case_count,
            rows=[metric.model_dump(mode="json") for metric in stored.rows],
            failures=[failure.model_dump(mode="json") for failure in stored.failures],
            generated_at=stored.generated_at,
        )
        async with self.sessions() as session:
            session.add(row)
            await session.commit()
        return stored

    async def get_latest_evaluation(self) -> EvaluationSummary | None:
        async with self.sessions() as session:
            row = await session.scalar(
                select(EvaluationRunRow).order_by(EvaluationRunRow.generated_at.desc()).limit(1)
            )
        if row is None:
            return None
        return EvaluationSummary(
            id=row.id,
            dataset_name=row.dataset_name,
            case_count=row.case_count,
            rows=[MetricRow.model_validate(item) for item in row.rows],
            failures=[FailureBucket.model_validate(item) for item in row.failures],
            generated_at=row.generated_at,
        )

    async def count_chunks(self) -> int:
        async with self.sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(ChunkRow)) or 0)

    async def count_retrieval_runs(self) -> int:
        async with self.sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(TraceRow)) or 0)

    @staticmethod
    async def _sync_document_task(session: AsyncSession, task: IndexTaskRow) -> None:
        document = await session.get(DocumentRow, task.document_id)
        if document is None:
            return
        document.status = task.status
        document.index_task_id = task.id
        document.index_progress = task.progress
        document.index_error = task.error_message
        document.updated_at = task.updated_at

    @staticmethod
    def _to_task(row: IndexTaskRow) -> IndexTask:
        return IndexTask(
            id=row.id,
            document_id=row.document_id,
            kind=row.kind,
            status=row.status,
            progress=row.progress,
            attempts=row.attempts,
            error_code=row.error_code,
            error_message=row.error_message,
            cancel_requested=row.cancel_requested,
            created_at=row.created_at,
            updated_at=row.updated_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )

    async def _new_embedding_rows(self, chunks: list[ChunkRecord]) -> list[EmbeddingRow]:
        if not chunks:
            return []
        vectors = await asyncio.to_thread(
            self.embedding_provider.embed_documents,
            [chunk.text for chunk in chunks],
        )
        return [
            EmbeddingRow(
                chunk_id=chunk.id,
                model_name=self.embedding_provider.name,
                embedding=self._validated_vector(vector),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

    @staticmethod
    def _validated_vector(vector: list[float]) -> list[float]:
        expected = get_settings().embedding_dimensions
        if len(vector) != expected:
            raise ValueError(f"Embedding 维度不匹配：期望 {expected}，实际 {len(vector)}")
        return vector

    @staticmethod
    def _new_chunk_rows(chunks: list[ChunkRecord]) -> list[ChunkRow]:
        return [
            ChunkRow(
                id=chunk.id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                strategy=chunk.strategy.value,
                position=index,
                page=chunk.page,
                heading_path=chunk.heading_path,
                text=chunk.text,
                tokens=chunk.tokens,
            )
            for index, chunk in enumerate(chunks)
        ]

    @staticmethod
    def _to_document(row: DocumentRow) -> DocumentSummary:
        return DocumentSummary(
            id=row.id,
            title=row.title,
            department=row.department,
            file_name=row.file_name,
            status=row.status,
            effective_date=row.effective_date,
            chunk_count=row.chunk_count,
            updated_at=row.updated_at,
            tags=row.tags,
            index_task_id=row.index_task_id,
            index_progress=row.index_progress,
            index_error=row.index_error,
        )

    @staticmethod
    def _to_chunk(row: ChunkRow) -> ChunkRecord:
        return ChunkRecord(
            id=row.id,
            document_id=row.document_id,
            document_title=row.document_title,
            strategy=row.strategy,
            page=row.page,
            heading_path=row.heading_path,
            text=row.text,
            tokens=row.tokens,
        )
