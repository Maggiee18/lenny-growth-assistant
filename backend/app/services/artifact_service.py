from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import AgentTurnResult, PodcastAgent, guard_generation, guard_retrieval
from app.agents.tools import (
    generate_html_artifact_tool,
    generate_markdown_artifact_tool,
    generate_ship30_tool,
    search_transcripts,
)
from app.core.errors import NotFoundError, ValidationAppError
from app.db.models import Artifact
from app.schemas.artifacts import ArtifactCreate
from app.services import session_service


async def create_artifact_from_agent_result(
    db: AsyncSession, session_id: uuid.UUID, message_id: uuid.UUID, result: AgentTurnResult
) -> Artifact:
    artifact = Artifact(
        session_id=session_id,
        message_id=message_id,
        artifact_type=result.artifact_type,
        title=result.artifact_title or "Untitled artifact",
        content=result.artifact_content or "",
        artifact_metadata={"validation_warnings": result.validation_warnings},
    )
    db.add(artifact)
    await db.flush()
    return artifact


def _parse_uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError) as exc:
        raise ValidationAppError(f"'{raw}' is not a valid artifact id.") from exc


async def get_artifact_or_404(db: AsyncSession, artifact_id: str) -> Artifact:
    aid = _parse_uuid(artifact_id)
    artifact = await db.get(Artifact, aid)
    if artifact is None:
        raise NotFoundError(f"Artifact {artifact_id} was not found.")
    return artifact


async def create_artifact_on_demand(db: AsyncSession, payload: ArtifactCreate, agent: PodcastAgent) -> Artifact:
    """POST /api/artifacts: generate an artifact outside the normal chat turn,
    e.g. "turn this conversation into a one-pager" without adding a new chat
    message. Reuses the same retrieval + skill tools the chat agent uses so
    grounding behavior is identical either way."""
    session = await session_service.get_session_or_404(db, str(payload.session_id))
    topic = payload.instructions or f"Summarize the conversation in session {session.id}"

    chunks = await guard_retrieval(
        search_transcripts(db, agent.embedding_provider, topic, agent.settings),
        provider_name=agent.embedding_provider.name,
    )

    if payload.artifact_type == "ship30":
        result = await guard_generation(
            generate_ship30_tool(agent.chat_provider, topic, chunks), provider_name=agent.chat_provider.name
        )
        content, title = result.artifact_markdown, result.artifact_title
    elif payload.artifact_type == "html":
        result = await guard_generation(
            generate_html_artifact_tool(agent.chat_provider, topic, chunks), provider_name=agent.chat_provider.name
        )
        content, title = result.artifact_html, result.artifact_title
    else:
        result = await guard_generation(
            generate_markdown_artifact_tool(agent.chat_provider, topic, chunks), provider_name=agent.chat_provider.name
        )
        content, title = result.artifact_markdown, result.artifact_title

    if not content:
        raise ValidationAppError(result.content)

    artifact = Artifact(
        session_id=session.id,
        message_id=payload.message_id,
        artifact_type=payload.artifact_type,
        title=title or "Untitled artifact",
        content=content,
        artifact_metadata={"validation_warnings": result.validation_warnings, "on_demand": True},
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact
