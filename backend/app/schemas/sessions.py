from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    user_id: str | None = Field(default=None, max_length=255)


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    provider: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionDetail(SessionSummary):
    messages: list["MessageOut"] = Field(default_factory=list)


from app.schemas.messages import MessageOut  # noqa: E402

SessionDetail.model_rebuild()
