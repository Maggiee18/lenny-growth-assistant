from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_db_session
from app.core.config import Settings
from app.schemas.sessions import SessionCreate, SessionDetail, SessionSummary
from app.schemas.messages import MessageOut
from app.services import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionSummary, status_code=201)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> SessionSummary:
    session = await session_service.create_session(db, payload, settings)
    return SessionSummary(
        id=session.id,
        title=session.title,
        provider=session.provider,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    user_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[SessionSummary]:
    rows = await session_service.list_sessions(db, user_id)
    return [
        SessionSummary(
            id=s.id,
            title=s.title,
            provider=s.provider,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=count,
        )
        for s, count in rows
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db_session)) -> SessionDetail:
    session = await session_service.get_session_with_messages_or_404(db, session_id)
    messages = [MessageOut.model_validate(m) for m in session.messages]
    return SessionDetail(
        id=session.id,
        title=session.title,
        provider=session.provider,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(messages),
        messages=messages,
    )
