from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db_session
from app.core.config import Settings
from app.schemas.config import ConfigResponse, HealthResponse
from app.services.health_service import build_config_response, build_health_response

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(
    db: AsyncSession = Depends(get_db_session), settings: Settings = Depends(get_app_settings)
) -> HealthResponse:
    return await build_health_response(db, settings)


@router.get("/api/config", response_model=ConfigResponse)
async def config(settings: Settings = Depends(get_app_settings)) -> ConfigResponse:
    return await build_config_response(settings)
