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

LENGTH IS A HARD REQUIREMENT: write at least 1100 words, targeting approximately 1250.
This is the single most important requirement below -- a short essay is a failed essay.
Do not wrap up early. If you feel you are close to a conclusion before reaching the target
length, that means you need to add more: another concrete example, a deeper elaboration of
one piece of evidence, a counterargument and rebuttal, or an additional practical sub-point.
Plan for roughly 6-8 substantial paragraphs across your sections, not 4-5 short ones.

Other requirements:
- Start with the hook, no throat-clearing preamble.
- Use at least 3 markdown headings (##) to keep it skimmable, each with multiple paragraphs
  underneath it -- a heading followed by one short paragraph is too thin.
- Use bullet lists where they aid scanning.
- Use **bold** selectively for the 2-4 most important phrases, not decoratively.
- Build a clear narrative: problem/tension -> evidence -> reframe -> practical insight.
- End with a concrete, specific, useful takeaway the reader can act on this week.
- Weave in the evidence's source titles naturally (e.g. "As discussed on ...") rather than
  a bare citation list -- this is a personal essay, not a report.

Return ONLY the markdown essay, no preamble, no code fences. Remember: aim for ~1250 words --
write the full essay, do not stop short.
"""

_CONTINUATION_PROMPT = """The essay above stops short of the ~1250-word target. Continue writing
directly from where it left off -- do not repeat the hook, any heading, or any sentence already
written. Add one or two more substantial paragraphs so the combined essay reaches approximately
1250 words.

GROUNDING RULE STILL APPLIES: do not introduce any new company, person, product, or anecdote that
is not already in the outline or the essay so far (e.g. do not reach for a famous unrelated example
like Airbnb, Uber, Netflix, etc. just to fill space). Add length by going deeper on the SAME
evidence already used -- more analysis, a counterargument to it, a sharper explanation of its
implication -- never by bringing in a new illustrative story of your own.

Return ONLY the new markdown to append (no repetition of prior content, no preamble, no code fences).
"""

# Word count below which we trigger one bounded continuation pass rather than
# accepting a short draft outright. Kept below the 938-word floor of the
# target band (see validator.py) so a draft that's merely a little short
# still gets accepted without the extra latency of a second CPU generation
# call -- continuation only fires when the shortfall is large enough to be
# worth ~another full generation's worth of time.
_CONTINUATION_TRIGGER_WORDS = 850
# Continuation is attempted exactly once per essay, never looped, so a model
# that keeps writing short is a bounded ~2x latency cost, not unbounded.
_MAX_CONTINUATION_ATTEMPTS = 1


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
    draft = await provider.chat(writer_messages, temperature=0.6, max_tokens=3200)
    markdown = draft.content.strip()
    markdown = re.sub(r"^```(?:markdown)?|```$", "", markdown, flags=re.MULTILINE).strip()

    for attempt in range(_MAX_CONTINUATION_ATTEMPTS):
        current_words = word_count(markdown)
        if current_words >= _CONTINUATION_TRIGGER_WORDS:
            break
        logger.info("ship30_continuation_triggered", attempt=attempt + 1, word_count=current_words)
        continuation_messages = [
            *writer_messages,
            ChatMessage(role="assistant", content=markdown),
            ChatMessage(role="user", content=_CONTINUATION_PROMPT),
        ]
        continuation = await provider.chat(continuation_messages, temperature=0.6, max_tokens=1600)
        addition = continuation.content.strip()
        addition = re.sub(r"^```(?:markdown)?|```$", "", addition, flags=re.MULTILINE).strip()
        if addition:
            markdown = f"{markdown}\n\n{addition}"

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
