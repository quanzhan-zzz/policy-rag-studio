from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PolicyRAG Studio API"
    app_version: str = "0.2.0"
    app_env: str = "development"
    api_cors_origins: str = "http://localhost:5173,http://localhost:4173"
    database_url: str = "postgresql+asyncpg://policyrag:policyrag@localhost:5432/policyrag"
    store_backend: Literal["memory", "postgres"] = "postgres"
    seed_demo_data: bool = True
    seed_official_data: bool = True
    redis_url: str = "redis://localhost:6379/0"
    index_task_stale_seconds: int = 300
    embedding_provider: Literal["hash", "openai", "bge"] = "hash"
    hash_embedding_dimensions: int = 1024
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 16
    bge_embedding_model: str = "BAAI/bge-m3"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None
    llm_api_base: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str | None = None
    llm_model: str = "glm-5.3-flash"
    reranker_provider: Literal["none", "heuristic", "llm", "bge"] = "heuristic"
    reranker_model: str | None = None
    bge_reranker_model: str = "BAAI/bge-reranker-base"
    reranker_api_base: str | None = None
    reranker_api_key: str | None = None
    reranker_timeout_seconds: float = 30.0
    query_planning_mode: Literal["none", "rewrite", "decompose"] = "none"
    query_planning_timeout_seconds: float = 15.0
    query_planning_max_subqueries: int = 4
    citation_verifier_provider: Literal["none", "rule", "llm"] = "none"
    citation_verifier_model: str | None = None
    citation_verifier_timeout_seconds: float = 15.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
