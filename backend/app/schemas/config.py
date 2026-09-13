from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthDependency(BaseModel):
    name: str
    healthy: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    dependencies: list[HealthDependency]


class ConfigResponse(BaseModel):
    provider: str
    model: str
    ollama_available: bool
    anthropic_configured: bool
    retrieval_top_k: int
    retrieval_similarity_threshold: float
