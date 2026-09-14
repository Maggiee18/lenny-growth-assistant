import pytest

from app.agents.tools import (
    NO_EVIDENCE_FOR_ARTIFACT_MESSAGE,
    generate_html_artifact_tool,
    generate_markdown_artifact_tool,
)
from app.core.errors import ArtifactSanitizationError
from app.providers.base import ChatMessage
from app.skills.artifacts.markdown import derive_title, validate_markdown
from app.skills.artifacts.sanitizer import sanitize_html


def test_sanitize_html_strips_script_tags():
    dirty = "<div>Hello</div><script>alert('xss')</script>"
    clean = sanitize_html(dirty)
    assert "<script" not in clean
    assert "alert" not in clean
    assert "<div>Hello</div>" in clean


def test_sanitize_html_strips_event_handlers():
    dirty = '<img src="x.png" onerror="alert(1)">'
    clean = sanitize_html(dirty)
    assert "onerror" not in clean


def test_sanitize_html_strips_javascript_urls():
    dirty = '<a href="javascript:alert(1)">click</a>'
    clean = sanitize_html(dirty)
    assert "javascript:" not in clean


def test_sanitize_html_strips_iframe_object_embed_form():
    dirty = (
        '<iframe src="https://evil.example"></iframe>'
        '<object data="x.swf"></object>'
        '<embed src="x.swf">'
        '<form action="https://evil.example"><input></form>'
    )
    clean = sanitize_html(dirty)
    for tag in ("iframe", "object", "embed", "<form"):
        assert tag not in clean


def test_sanitize_html_allows_safe_structural_tags_and_inline_style():
    safe = "<h1>Title</h1><p>Some <strong>bold</strong> text.</p><style>.a{color:red}</style>"
    clean = sanitize_html(safe)
    assert "<h1>" in clean
    assert "<strong>" in clean


def test_sanitize_html_rejects_oversized_payload():
    huge = "<p>" + ("a" * 300_000) + "</p>"
    with pytest.raises(ArtifactSanitizationError):
        sanitize_html(huge, max_bytes=1000)


def test_validate_markdown_rejects_script_tags():
    with pytest.raises(ArtifactSanitizationError):
        validate_markdown("# Title\n\n<script>alert(1)</script>")


def test_validate_markdown_rejects_empty():
    with pytest.raises(ArtifactSanitizationError):
        validate_markdown("   ")


def test_derive_title_from_heading():
    assert derive_title("# My Great Essay\n\nBody text") == "My Great Essay"


def test_derive_title_fallback_when_no_heading():
    assert derive_title("just body text, no heading") == "Untitled artifact"


async def test_create_artifact_endpoint_generates_markdown(client, db_session):
    from app.db.models import TranscriptChunk, TranscriptDocument

    doc = TranscriptDocument(title="Pricing", episode="Ep 2", source_url="https://x.test", content_hash="h1")
    db_session.add(doc)
    await db_session.flush()
    db_session.add(
        TranscriptChunk(document_id=doc.id, chunk_index=0, content="Pricing should map to value metric.", embedding=[1] * 8)
    )
    await db_session.commit()

    session = (await client.post("/api/sessions", json={})).json()
    resp = await client.post(
        "/api/artifacts",
        json={"session_id": session["id"], "artifact_type": "markdown", "instructions": "Summarize pricing advice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["artifact_type"] == "markdown"
    assert body["content"]


async def test_get_artifact_not_found(client):
    from tests.conftest import random_uuid_str

    resp = await client.get(f"/api/artifacts/{random_uuid_str()}")
    assert resp.status_code == 404


async def test_markdown_artifact_abstains_with_no_chunks_and_no_history(fake_chat_provider):
    """Regression test for a live bug: asking for an artifact with neither
    matching transcript evidence nor conversation history used to produce a
    nonsense artifact literally titled "No Transcript Excerpts Provided"
    instead of refusing. See agents/tools.py NO_EVIDENCE_FOR_ARTIFACT_MESSAGE."""
    result = await generate_markdown_artifact_tool(fake_chat_provider, "Summarize this conversation", [], [])
    assert result.abstained is True
    assert result.content == NO_EVIDENCE_FOR_ARTIFACT_MESSAGE
    assert result.artifact_markdown is None


async def test_html_artifact_abstains_with_no_chunks_and_no_history(fake_chat_provider):
    result = await generate_html_artifact_tool(fake_chat_provider, "Make a page about nothing", [], [])
    assert result.abstained is True
    assert result.content == NO_EVIDENCE_FOR_ARTIFACT_MESSAGE
    assert result.artifact_html is None


async def test_markdown_artifact_grounds_in_conversation_history_when_no_chunks(fake_chat_provider):
    """"Summarize this conversation" has no transcript-shaped retrieval query,
    but should still work when there's real prior chat to summarize."""
    history = [
        ChatMessage(role="user", content="What do guests say about pricing?"),
        ChatMessage(role="assistant", content="Guests recommend anchoring price to the value metric."),
    ]
    result = await generate_markdown_artifact_tool(fake_chat_provider, "Summarize this conversation", [], history)
    assert result.abstained is False
    assert result.artifact_markdown is not None
    # The conversation content should have been sent to the model as grounding material.
    sent_content = fake_chat_provider.last_messages[-1].content
    assert "value metric" in sent_content


async def test_create_artifact_endpoint_abstains_gracefully_for_empty_session(client):
    """/api/artifacts on a brand-new session with no messages and a topic that
    matches no transcripts should fail with a clear validation error, not a
    500 or a nonsense artifact."""
    session = (await client.post("/api/sessions", json={})).json()
    resp = await client.post(
        "/api/artifacts",
        json={"session_id": session["id"], "artifact_type": "markdown"},
    )
    assert resp.status_code == 422
    assert "enough grounded material" in resp.json()["error"]["message"]
