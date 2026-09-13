from __future__ import annotations

import json
import re

from app.core.logging import get_logger
from app.providers.base import ChatMessage, LLMProvider
from app.retrieval.retriever import RetrievedChunk
from app.skills.ship30.schema import EvidencePoint, Ship30Outline, Ship30Result
from app.skills.ship30.validator import validate_structure, word_count

logger = get_logger(__name__)


class InsufficientEvidenceError(Exception):
    pass


_OUTLINE_SYSTEM_PROMPT = """You are a research editor preparing an outline for a Ship 30 for 30 style essay.
You must work ONLY from the provided transcript excerpts. Do not use outside knowledge.
Respond with ONLY a JSON object (no markdown fences, no commentary) matching this shape:
{
  "central_insight": "...",
  "tension_or_problem": "...",
  "evidence": [{"claim": "...", "source_title": "...", "source_excerpt": "..."}],
  "hook": "...",
  "practical_insight": "...",
  "takeaway": "..."
}
Every "source_excerpt" must be copied verbatim (or near-verbatim) from the excerpts given to you.
If the excerpts do not support a coherent essay topic, return an empty "evidence" list.
"""

_WRITER_SYSTEM_PROMPT = """You are a Ship 30 for 30 essay writer. Using ONLY the structured outline provided
(never invent new facts or stories beyond it), write a complete essay in Markdown.

Requirements:
- Approximately 1250 words.
- Start with the hook, no throat-clearing preamble.
- Use at least 2 markdown headings (##) to keep it skimmable.
- Use bullet lists where they aid scanning.
- Use **bold** selectively for the 2-4 most important phrases, not decoratively.
- Build a clear narrative: problem/tension -> evidence -> reframe -> practical insight.
- End with a concrete, specific, useful takeaway the reader can act on this week.
- Weave in the evidence's source titles naturally (e.g. "As discussed on ...") rather than
  a bare citation list -- this is a personal essay, not a report.
Return ONLY the markdown essay, no preamble, no code fences.
"""


def _format_excerpts(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[Source: {c.title}{f' ({c.episode})' if c.episode else ''}]\n{c.content}" for c in chunks
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


async def _build_outline(provider: LLMProvider, topic: str, chunks: list[RetrievedChunk]) -> Ship30Outline:
    messages = [
        ChatMessage(role="system", content=_OUTLINE_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=f"Topic/question: {topic}\n\nTranscript excerpts:\n{_format_excerpts(chunks)}",
        ),
    ]
    result = await provider.chat(messages, temperature=0.4, max_tokens=1200)
    try:
        data = _extract_json(result.content)
        outline = Ship30Outline(
            central_insight=data.get("central_insight", ""),
            tension_or_problem=data.get("tension_or_problem", ""),
            evidence=[EvidencePoint(**e) for e in data.get("evidence", [])],
            hook=data.get("hook", ""),
            practical_insight=data.get("practical_insight", ""),
            takeaway=data.get("takeaway", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("ship30_outline_parse_failed", error=str(exc), raw=result.content[:500])
        raise InsufficientEvidenceError("Could not build a grounded outline from retrieved evidence.") from exc

    if len(outline.evidence) < 2:
        raise InsufficientEvidenceError(
            "Retrieved transcript evidence was too thin to support a grounded Ship 30 essay."
        )
    return outline


async def generate_ship30(
    provider: LLMProvider, topic: str, chunks: list[RetrievedChunk]
) -> Ship30Result:
    if len(chunks) < 2:
        raise InsufficientEvidenceError(
            "I couldn't find enough evidence in the Lenny transcript knowledge base to write a "
            "grounded Ship 30 essay on this topic."
        )

    outline = await _build_outline(provider, topic, chunks)

    writer_messages = [
        ChatMessage(role="system", content=_WRITER_SYSTEM_PROMPT),
        ChatMessage(role="user", content=f"Outline JSON:\n{outline.model_dump_json(indent=2)}"),
    ]
    draft = await provider.chat(writer_messages, temperature=0.6, max_tokens=2600)
    markdown = draft.content.strip()
    markdown = re.sub(r"^```(?:markdown)?|```$", "", markdown, flags=re.MULTILINE).strip()

    warnings = validate_structure(markdown)
    title = outline.central_insight.strip() or topic
    if len(title) > 120:
        title = title[:117] + "..."

    return Ship30Result(
        title=title,
        markdown=markdown,
        word_count=word_count(markdown),
        outline=outline,
        validation_warnings=warnings,
    )
