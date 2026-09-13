"""Application configuration.

All runtime configuration flows through this single Settings object, loaded
from environment variables (see .env.example). Nothing here hard-codes a
secret; missing optional values degrade a feature rather than crash startup
(see core.startup for the explicit validation pass).
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderName(str, Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"


def _default_transcripts_dir() -> str:
    """Repo-root-relative default that works both from source and in Docker.

    This file lives at backend/app/core/config.py, so its 3rd parent is the
    repo root when running from source (`backend/` is a normal subdirectory).
    Inside the container, only backend/'s contents are copied to /app, so
    this file lives at /app/app/core/config.py and the 3rd parent is "/" --
    which is exactly why docker-compose.yml bind-mounts the host's ./data to
    the container's /data (not /app/data): both cases resolve to the same
    "<3 parents up>/data/transcripts" shape with zero special-casing.
    """
    return str(Path(__file__).resolve().parents[3] / "data" / "transcripts")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "The Lenny Growth Assistant"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_cors_origins: str = "http://localhost:3000"

    # --- Database (required) ---
    database_url: str = Field(
        default="postgresql+asyncpg://lenny:lenny@localhost:5432/lenny_growth_assistant",
        description="Async SQLAlchemy URL used by the app at runtime.",
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg2://lenny:lenny@localhost:5432/lenny_growth_assistant",
        description="Sync URL used by Alembic migrations.",
    )

    # --- Provider selection ---
    llm_provider: LLMProviderName = LLMProviderName.OLLAMA

    # --- Ollama (local, required for the default demo path) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 90.0

    # --- Anthropic (cloud, optional) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    anthropic_timeout_seconds: float = 60.0

    # --- Retrieval ---
    retrieval_top_k: int = 6
    retrieval_similarity_threshold: float = 0.55
    embedding_dimensions: int = 768
    chunk_target_tokens: int = 350
    chunk_overlap_tokens: int = 60

    # --- Artifacts ---
    artifact_max_html_bytes: int = 200_000

    # --- Ingestion ---
    transcripts_dir: str = Field(default_factory=_default_transcripts_dir)

    @field_validator("api_cors_origins")
    @classmethod
    def _non_empty_origins(cls, v: str) -> str:
        return v or "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
