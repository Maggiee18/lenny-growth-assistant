from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import PodcastAgent
from app.core.logging import get_logger
from app.db.models import Message, Session
from app.providers.base import ChatMessage
from app.schemas.messages import MessageCreate, MessageResponse, MessageOut, SourceCitation
from app.services.artifact_service import create_artifact_from_agent_result
from app.services.session_service import touch_session

logger = get_logger(__name__)

_HISTORY_LIMIT = 12  # most recent turns kept as context for follow-ups


async def _load_history(db: AsyncSession, session_id) -> list[ChatMessage]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = list(reversed((await db.execute(stmt)).scalars().all()))
    return [ChatMessage(role=m.role, content=m.content) for m in rows if m.role in ("user", "assistant")]


async def post_message(
    db: AsyncSession,
    session: Session,
    payload: MessageCreate,
    agent: PodcastAgent,
) -> MessageResponse:
    history = await _load_history(db, session.id)

    user_message = Message(session_id=session.id, role="user", content=payload.content)
    db.add(user_message)
    await db.flush()

    result = await agent.handle_turn(db, payload.content, history)

    assistant_metadata = {
        "intent": result.intent.value,
        "abstained": result.abstained,
        "retrieval_latency_ms": result.retrieval_latency_ms,
        "generation_latency_ms": result.generation_latency_ms,
        "sources": [
            {
                "document_id": str(s.document_id),
                "chunk_id": str(s.chunk_id),
                "title": s.title,
                "episode": s.episode,
                "source_url": s.source_url,
                "excerpt": s.content[:400],
                "relevance_score": s.relevance_score,
                "retrieval_method": s.retrieval_method,
            }
            for s in result.sources
        ],
    }
    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content=result.content,
        message_metadata=assistant_metadata,
    )
    db.add(assistant_message)
    await db.flush()

    artifact_id = None
    if result.artifact_type and result.artifact_content:
        artifact = await create_artifact_from_agent_result(db, session.id, assistant_message.id, result)
        artifact_id = artifact.id

    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)
    await touch_session(db, session)

    return MessageResponse(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        sources=[
            SourceCitation(
                document_id=s.document_id,
                chunk_id=s.chunk_id,
                title=s.title,
                episode=s.episode,
                source_url=s.source_url,
                excerpt=s.content[:400],
                relevance_score=s.relevance_score,
            )
            for s in result.sources
        ],
        abstained=result.abstained,
        artifact_id=artifact_id,
        provider=agent.chat_provider.name,
        model=agent.chat_provider.model,
    )
