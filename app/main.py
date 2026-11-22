from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db.postgres import PostgresStore
from app.services.task_publisher import CeleryTaskPublisher, NoopTaskPublisher
from app.store import InMemoryStore

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.store_backend == "memory":
        repo = InMemoryStore()
        publisher = NoopTaskPublisher()
    else:
        repo = await PostgresStore.create(
            settings.database_url,
            seed_demo_data=settings.seed_demo_data,
        )
        publisher = CeleryTaskPublisher()
    app.state.store = repo
    app.state.task_publisher = publisher
    try:
        yield
    finally:
        await repo.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "PolicyRAG Studio API with selectable in-memory and PostgreSQL repository adapters."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "PolicyRAG Studio",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
