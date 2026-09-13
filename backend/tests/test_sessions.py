from tests.conftest import random_uuid_str


async def test_create_session_returns_defaults(client):
    resp = await client.post("/api/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "New chat"
    assert body["message_count"] == 0
    assert "id" in body


async def test_create_session_with_custom_title(client):
    resp = await client.post("/api/sessions", json={"title": "Growth strategy Q1"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Growth strategy Q1"


async def test_list_sessions_returns_created_sessions(client):
    await client.post("/api/sessions", json={"title": "A"})
    await client.post("/api/sessions", json={"title": "B"})
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    titles = {s["title"] for s in resp.json()}
    assert {"A", "B"} <= titles


async def test_get_session_not_found_returns_404_with_error_category(client):
    resp = await client.get(f"/api/sessions/{random_uuid_str()}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["category"] == "not_found"


async def test_get_session_with_malformed_uuid_returns_422(client):
    resp = await client.get("/api/sessions/not-a-uuid")
    assert resp.status_code == 422
    assert resp.json()["error"]["category"] == "validation_error"


async def test_sessions_are_isolated_from_each_other(client):
    s1 = (await client.post("/api/sessions", json={"title": "Session 1"})).json()
    s2 = (await client.post("/api/sessions", json={"title": "Session 2"})).json()

    await client.post(f"/api/sessions/{s1['id']}/messages", json={"content": "What is activation?"})

    detail1 = (await client.get(f"/api/sessions/{s1['id']}")).json()
    detail2 = (await client.get(f"/api/sessions/{s2['id']}")).json()

    assert len(detail1["messages"]) == 2  # user + assistant
    assert len(detail2["messages"]) == 0
