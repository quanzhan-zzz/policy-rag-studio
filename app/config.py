from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PolicyRAG Studio API"
    app_env: str = "development"
    api_cors_origins: str = "http://localhost:5173,http://localhost:4173"
    database_url: str = "postgresql+asyncpg://policyrag:policyrag@localhost:5432/policyrag"
    redis_url: str = "redis://localhost:6379/0"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
