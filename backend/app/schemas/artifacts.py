from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    session_id: uuid.UUID
    artifact_type: Literal["markdown", "html", "ship30"]
    instructions: str | None = Field(default=None, max_length=2000)
    message_id: uuid.UUID | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID | None
    message_id: uuid.UUID | None
    artifact_type: str
    title: str
    content: str
    artifact_metadata: dict = Field(default_factory=dict)
    created_at: datetime
