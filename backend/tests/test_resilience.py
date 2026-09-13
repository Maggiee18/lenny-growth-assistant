"""Dependency-failure resilience (see architecture.md "Failure handling").

These pin down the behavior found via manual smoke-testing: a raw
httpx.ConnectError from a down Ollama must never reach the client as a bare
500 -- it has to come back as a structured, categorized error the frontend
can render as an understandable message.
"""
import httpx
import pytest

from app.agents.agent import PodcastAgent
from app.core.config import get_settings
from app.core.errors import ModelFailureError, RetrievalError
from app.db.models import TranscriptChunk, TranscriptDocument
from app.providers.base import ChatMessage


class _DownProvider:
    name = "ollama"
    model = "llama3.1:8b"

    async def chat(self, *args, **kwargs):
        raise httpx.ConnectError("All connection attempts failed")

    async def is_available(self):
        return False, "down"


class _DownEmbeddingProvider:
    name = "ollama-embeddings"
    dimensions = 8

    async def embed(self, texts):
        raise httpx.ConnectError("All connection attempts failed")

    async def is_available(self):
        return False, "down"


async def test_chat_generation_failure_becomes_model_failure_error(db_session, fake_embedding_provider):
    # Generation is only reached when retrieval finds evidence -- seed a
    # chunk that matches the query embedding so answer_from_sources actually
    # calls the (down) chat provider instead of abstaining early.
    [vector] = await fake_embedding_provider.embed(["What is activation?"])
    doc = TranscriptDocument(title="Activation", content_hash="h-resilience")
    db_session.add(doc)
    await db_session.flush()
    db_session.add(TranscriptChunk(document_id=doc.id, chunk_index=0, content="Activation content.", embedding=vector))
    await db_session.commit()

    agent = PodcastAgent(_DownProvider(), fake_embedding_provider, get_settings())
    with pytest.raises(ModelFailureError) as exc_info:
        await agent.handle_turn(db_session, "What is activation?", [])
    assert "unavailable" in str(exc_info.value).lower()
    assert exc_info.value.detail is not None


async def test_embedding_failure_becomes_retrieval_error(db_session, fake_chat_provider):
    agent = PodcastAgent(fake_chat_provider, _DownEmbeddingProvider(), get_settings())
    with pytest.raises(RetrievalError):
        await agent.handle_turn(db_session, "What is activation?", [])


async def test_message_endpoint_returns_structured_error_when_ollama_down(client, db_session):
    from app.api.deps import get_agent
    from app.main import app

    session_resp = await client.post("/api/sessions", json={})
    session_id = session_resp.json()["id"]

    down_agent = PodcastAgent(_DownProvider(), _DownEmbeddingProvider(), get_settings())
    app.dependency_overrides[get_agent] = lambda: down_agent
    try:
        resp = await client.post(f"/api/sessions/{session_id}/messages", json={"content": "hello"})
    finally:
        del app.dependency_overrides[get_agent]

    assert resp.status_code in (502, 503)
    body = resp.json()
    assert body["error"]["category"] in ("model_failure", "retrieval_failure")
