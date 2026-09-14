from app.db.models import TranscriptChunk, TranscriptDocument
from tests.conftest import random_uuid_str


async def _seed_document(db_session, embedding, title="Activation Basics", content="Activation is the moment a user first gets value."):
    doc = TranscriptDocument(title=title, episode="Ep 1", source_url="https://example.com/ep1", content_hash=title)
    db_session.add(doc)
    await db_session.flush()
    chunk = TranscriptChunk(
        document_id=doc.id,
        chunk_index=0,
        content=content,
        embedding=embedding,
        chunk_metadata={},
    )
    db_session.add(chunk)
    await db_session.commit()
    return doc, chunk


QUESTION = "What is activation?"


async def test_post_message_without_evidence_abstains(client):
    session = (await client.post("/api/sessions", json={})).json()
    resp = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": QUESTION})
    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is True
    assert "couldn't find enough evidence" in body["assistant_message"]["content"]
    assert body["sources"] == []


async def test_post_message_with_evidence_returns_grounded_answer_and_sources(client, db_session, fake_embedding_provider):
    [query_vector] = await fake_embedding_provider.embed([QUESTION])
    await _seed_document(db_session, embedding=query_vector)

    session = (await client.post("/api/sessions", json={})).json()
    resp = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": QUESTION})
    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is False
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["title"] == "Activation Basics"


async def test_post_message_validates_blank_content(client):
    session = (await client.post("/api/sessions", json={})).json()
    resp = await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "   "})
    assert resp.status_code == 422


async def test_post_message_to_missing_session_returns_404(client):
    resp = await client.post(f"/api/sessions/{random_uuid_str()}/messages", json={"content": "hello"})
    assert resp.status_code == 404


async def test_followup_question_has_prior_turn_in_history(client, db_session, fake_chat_provider, fake_embedding_provider):
    [query_vector] = await fake_embedding_provider.embed([QUESTION])
    await _seed_document(db_session, embedding=query_vector)

    session = (await client.post("/api/sessions", json={})).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": QUESTION})
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "Can you say more about that?"})

    history = [(m.role, m.content) for m in fake_chat_provider.last_messages]
    assert any(role == "user" and QUESTION in content for role, content in history)


async def test_message_persists_role_and_content(client):
    session = (await client.post("/api/sessions", json={})).json()
    await client.post(f"/api/sessions/{session['id']}/messages", json={"content": "hello there"})
    detail = (await client.get(f"/api/sessions/{session['id']}")).json()
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "hello there"
    assert detail["messages"][1]["role"] == "assistant"


async def test_artifact_id_is_recoverable_after_reopening_a_session(client, db_session, fake_embedding_provider):
    """Regression test: reopening a past session used to lose the link to
    any artifact it generated -- the frontend had no way to know a message
    had one, since artifact_id was only ever returned in the original POST
    response, never persisted onto the message itself."""
    [query_vector] = await fake_embedding_provider.embed(["Create a markdown one-pager summarizing pricing"])
    await _seed_document(db_session, embedding=query_vector, title="Pricing Advice")

    session = (await client.post("/api/sessions", json={})).json()
    post_resp = await client.post(
        f"/api/sessions/{session['id']}/messages",
        json={"content": "Create a markdown one-pager summarizing pricing"},
    )
    body = post_resp.json()
    assert body["artifact_id"] is not None

    detail = (await client.get(f"/api/sessions/{session['id']}")).json()
    assistant_msg = detail["messages"][-1]
    assert assistant_msg["message_metadata"]["artifact_id"] == body["artifact_id"]
    assert assistant_msg["message_metadata"]["sources"]  # citations also recoverable on reload
