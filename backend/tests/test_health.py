async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "down")
    names = {d["name"] for d in body["dependencies"]}
    assert "database" in names


async def test_health_reports_database_dependency_name_and_shape(client):
    resp = await client.get("/health")
    body = resp.json()
    db_dep = next(d for d in body["dependencies"] if d["name"] == "database")
    assert db_dep["healthy"] is True


async def test_config_endpoint_exposes_provider_without_secrets(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "provider" in body
    assert "model" in body
    assert "anthropic_api_key" not in body
    assert "api_key" not in str(body).lower()
