from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db.models import ChunkRow, DocumentRow, TraceRow
from app.schemas import ChunkRecord, ChunkStrategy, DocumentSummary, TraceRecord, TraceStage
from app.services.chunking import chunk_document
from app.services.parsing import parse_document
from app.services.seed import SEED_DOCUMENTS
from app.services.text import tokenize


class PostgresStore:
    """PostgreSQL repository adapter for documents, chunks, and traces."""

    backend = "postgres"

    def __init__(
        self,
        engine: AsyncEngine,
        sessions: async_sessionmaker[AsyncSession],
    ) -> None:
        self.engine = engine
        self.sessions = sessions

    @classmethod
    async def create(
        cls,
        database_url: str,
        *,
        seed_demo_data: bool = True,
    ) -> "PostgresStore":
        engine = create_async_engine(database_url, pool_pre_ping=True)
        store = cls(engine, async_sessionmaker(engine, expire_on_commit=False))
        await store.initialize(seed_demo_data=seed_demo_data)
        return store

    async def initialize(self, *, seed_demo_data: bool) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if seed_demo_data:
            await self._seed()

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
            status="indexed",
            effective_date=effective_date,
            content_text=content_text,
            chunk_count=0,
            updated_at=now,
            tags=tags,
        )
        for strategy in ChunkStrategy:
            chunks = chunk_document(content_text, document_id, title, strategy)
            if strategy is ChunkStrategy.HEADING:
                document.chunk_count = len(chunks)
            document.chunks.extend(self._new_chunk_rows(chunks))
        async with self.sessions() as session:
            session.add(document)
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
            session.add_all(all_new_chunks)
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

    async def count_chunks(self) -> int:
        async with self.sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(ChunkRow)) or 0)

    async def count_retrieval_runs(self) -> int:
        async with self.sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(TraceRow)) or 0)

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
