from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db_session, get_emb_provider
from app.core.config import Settings
from app.providers.base import EmbeddingProvider
from app.schemas.ingestion import IngestionRunRequest, IngestionRunResponse
from app.ingestion.pipeline import run_ingestion

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post("/run", response_model=IngestionRunResponse)
async def run(
    payload: IngestionRunRequest,
    db: AsyncSession = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_emb_provider),
    settings: Settings = Depends(get_app_settings),
) -> IngestionRunResponse:
    source_dir = Path(payload.source_dir) if payload.source_dir else Path(settings.transcripts_dir)
    return await run_ingestion(
        db,
        embedding_provider,
        source_dir,
        force_reingest=payload.force_reingest,
        chunk_target_tokens=settings.chunk_target_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
    )
