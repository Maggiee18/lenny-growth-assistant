from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import PodcastAgent
from app.api.deps import get_agent, get_db_session
from app.schemas.artifacts import ArtifactCreate, ArtifactOut
from app.services import artifact_service

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.post("", response_model=ArtifactOut, status_code=201)
async def create_artifact(
    payload: ArtifactCreate,
    db: AsyncSession = Depends(get_db_session),
    agent: PodcastAgent = Depends(get_agent),
) -> ArtifactOut:
    artifact = await artifact_service.create_artifact_on_demand(db, payload, agent)
    return ArtifactOut.model_validate(artifact)


@router.get("/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: str, db: AsyncSession = Depends(get_db_session)) -> ArtifactOut:
    artifact = await artifact_service.get_artifact_or_404(db, artifact_id)
    return ArtifactOut.model_validate(artifact)
