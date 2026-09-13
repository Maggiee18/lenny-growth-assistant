from __future__ import annotations

from pydantic import BaseModel


class IngestionRunRequest(BaseModel):
    source_dir: str | None = None
    force_reingest: bool = False


class IngestionRunResponse(BaseModel):
    documents_seen: int
    documents_ingested: int
    documents_skipped_duplicate: int
    chunks_created: int
    errors: list[str]
