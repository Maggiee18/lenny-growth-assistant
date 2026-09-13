from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import Message, Session
from app.schemas.sessions import SessionCreate


async def create_session(db: AsyncSession, payload: SessionCreate, settings: Settings) -> Session:
    session = Session(
        title=(payload.title or "New chat").strip()[:500] or "New chat",
        user_id=payload.user_id,
        provider=settings.llm_provider.value,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: str | None = None) -> list[tuple[Session, int]]:
    stmt = (
        select(Session, func.count(Message.id).label("message_count"))
        .outerjoin(Message, Message.session_id == Session.id)
        .group_by(Session.id)
        .order_by(Session.updated_at.desc())
    )
    if user_id:
        stmt = stmt.where(Session.user_id == user_id)
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


def _parse_uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError) as exc:
        raise ValidationAppError(f"'{raw}' is not a valid session id.") from exc


async def get_session_or_404(db: AsyncSession, session_id: str) -> Session:
    sid = _parse_uuid(session_id)
    session = await db.get(Session, sid)
    if session is None:
        raise NotFoundError(f"Session {session_id} was not found.")
    return session


async def get_session_with_messages_or_404(db: AsyncSession, session_id: str) -> Session:
    sid = _parse_uuid(session_id)
    stmt = select(Session).where(Session.id == sid).options(selectinload(Session.messages))
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise NotFoundError(f"Session {session_id} was not found.")
    return session


async def touch_session(db: AsyncSession, session: Session) -> None:
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
