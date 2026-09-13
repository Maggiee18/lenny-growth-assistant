from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceCitation(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    episode: str | None = None
    source_url: str | None = None
    excerpt: str
    relevance_score: float


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message content must not be blank.")
        return v


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    message_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MessageResponse(BaseModel):
    """What the API returns after a user message is answered by the agent."""

    user_message: MessageOut
    assistant_message: MessageOut
    sources: list[SourceCitation] = Field(default_factory=list)
    abstained: bool = False
    artifact_id: uuid.UUID | None = None
    provider: str
    model: str
