from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PolicyRAG Studio API"
    app_env: str = "development"
    api_cors_origins: str = "http://localhost:5173,http://localhost:4173"
    database_url: str = "postgresql+asyncpg://policyrag:policyrag@localhost:5432/policyrag"
    redis_url: str = "redis://localhost:6379/0"
    embedding_provider: Literal["hash", "openai", "bge"] = "hash"
    hash_embedding_dimensions: int = 192
    bge_embedding_model: str = "BAAI/bge-m3"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_api_key: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
