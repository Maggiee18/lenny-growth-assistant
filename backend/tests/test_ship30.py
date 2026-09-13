import json
import uuid

import pytest

from app.providers.base import ChatMessage, ChatResult
from app.retrieval.retriever import RetrievedChunk
from app.skills.ship30.validator import validate_structure, word_count
from app.skills.ship30.writer import InsufficientEvidenceError, generate_ship30


def _chunk(title="Ep 1", content="Activation matters more than acquisition."):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        episode=None,
        source_url="https://example.com",
        content=content,
        relevance_score=0.9,
        retrieval_method="vector",
    )


class _ScriptedProvider:
    """Returns queued responses in order -- outline JSON, then essay markdown."""

    name = "scripted"
    model = "scripted-model"

    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    async def chat(self, messages, *, tools=None, temperature=0.3, max_tokens=2000):
        content = self._responses.pop(0)
        return ChatResult(content=content, tool_calls=[], raw_model=self.model, stop_reason="stop")


def _valid_outline_json() -> str:
    return json.dumps(
        {
            "central_insight": "Activation beats acquisition",
            "tension_or_problem": "Teams over-invest in top of funnel",
            "evidence": [
                {"claim": "Activation matters more", "source_title": "Ep 1", "source_excerpt": "Activation matters more than acquisition."},
                {"claim": "Fix the funnel", "source_title": "Ep 1", "source_excerpt": "Activation matters more than acquisition."},
            ],
            "hook": "Everyone is fixing the wrong leak.",
            "practical_insight": "Find the first honest win.",
            "takeaway": "Audit your activation funnel this week.",
        }
    )


def _valid_essay_markdown() -> str:
    body = "\n\n".join(
        [
            "Everyone is fixing the wrong leak in their funnel.",
            "## The real problem",
            "Teams chase acquisition when **activation** is broken.",
            "- Fix the first step\n- Then worry about scale",
            "## What actually works",
            "Find the **first honest win** and sequence experience before configuration.",
            "## Takeaway",
            "Audit your activation funnel this week and fix the worst single step.",
        ]
        * 20  # comfortably above the 850-word continuation trigger, so this
        # fixture exercises the "no continuation needed" path
    )
    return body


async def test_generate_ship30_raises_when_fewer_than_two_chunks():
    provider = _ScriptedProvider([])
    with pytest.raises(InsufficientEvidenceError):
        await generate_ship30(provider, "growth loops", [_chunk()])


async def test_generate_ship30_raises_when_outline_has_insufficient_evidence():
    thin_outline = json.dumps(
        {
            "central_insight": "x",
            "tension_or_problem": "y",
            "evidence": [],
            "hook": "h",
            "practical_insight": "p",
            "takeaway": "t",
        }
    )
    provider = _ScriptedProvider([thin_outline])
    with pytest.raises(InsufficientEvidenceError):
        await generate_ship30(provider, "growth loops", [_chunk(), _chunk(title="Ep 2")])


async def test_generate_ship30_happy_path_returns_result_with_outline_and_markdown():
    provider = _ScriptedProvider([_valid_outline_json(), _valid_essay_markdown()])
    chunks = [_chunk(), _chunk(title="Ep 2")]
    result = await generate_ship30(provider, "growth loops", chunks)

    assert result.outline.central_insight == "Activation beats acquisition"
    assert len(result.outline.evidence) == 2
    assert result.word_count > 0
    assert "## " in result.markdown


async def test_generate_ship30_triggers_one_continuation_when_draft_is_short():
    short_draft = "word " * 200  # well under the 850-word continuation trigger
    continuation_text = "word " * 200
    provider = _ScriptedProvider([_valid_outline_json(), short_draft, continuation_text])
    chunks = [_chunk(), _chunk(title="Ep 2")]

    result = await generate_ship30(provider, "growth loops", chunks)

    # Both the original draft's and the continuation's words should be present.
    assert result.word_count >= 380
    assert provider._responses == []  # exactly 3 calls consumed: outline, draft, one continuation


async def test_generate_ship30_does_not_continue_past_the_trigger_threshold():
    long_enough_draft = "word " * 900  # already above the 850-word trigger
    provider = _ScriptedProvider([_valid_outline_json(), long_enough_draft])
    chunks = [_chunk(), _chunk(title="Ep 2")]

    result = await generate_ship30(provider, "growth loops", chunks)

    assert result.word_count == 900
    assert provider._responses == []  # only 2 calls: outline + draft, no continuation call queued or consumed


def test_word_count_ignores_markdown_punctuation():
    assert word_count("# Title\n\nSome **bold** text here.") == 5  # Title Some bold text here.


def test_validate_structure_flags_missing_headings_and_bullets():
    warnings = validate_structure("Just one paragraph with no structure at all.")
    assert any("heading" in w.lower() for w in warnings)
    assert any("bullet" in w.lower() for w in warnings)


def test_validate_structure_passes_well_formed_essay_word_count_band():
    essay = ("word " * 1250) + "\n\n## Heading one\n\n## Heading two\n\n- bullet one\n- bullet two\n\n**bold one** **bold two**"
    warnings = validate_structure(essay)
    assert not any("word count" in w.lower() for w in warnings)
