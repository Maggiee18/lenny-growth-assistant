from __future__ import annotations

from pydantic import BaseModel, Field


class EvidencePoint(BaseModel):
    claim: str
    source_title: str
    source_excerpt: str


class Ship30Outline(BaseModel):
    """Structured intermediate output of pipeline stage 1 (see skill.md).

    Kept as an explicit, validated object -- not free text -- so stage 2
    (the writer) cannot silently drop the "insight -> tension -> evidence"
    structure the Ship 30 for 30 format depends on, and so we can reject an
    outline outright if the model invented evidence not tied to a retrieved
    source.
    """

    central_insight: str
    tension_or_problem: str
    evidence: list[EvidencePoint] = Field(default_factory=list)
    hook: str
    practical_insight: str
    takeaway: str


class Ship30Result(BaseModel):
    title: str
    markdown: str
    word_count: int
    outline: Ship30Outline
    validation_warnings: list[str] = Field(default_factory=list)
