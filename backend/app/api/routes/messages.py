from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import PodcastAgent
from app.api.deps import get_agent, get_db_session
from app.core.logging import get_logger
from app.schemas.messages import MessageCreate, MessageResponse
from app.services import message_service, session_service

router = APIRouter(prefix="/api/sessions", tags=["messages"])
logger = get_logger(__name__)


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def post_message(
    session_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    agent: PodcastAgent = Depends(get_agent),
) -> MessageResponse:
    session = await session_service.get_session_or_404(db, session_id)
    return await message_service.post_message(db, session, payload, agent)
