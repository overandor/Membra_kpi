from fastapi.testclient import TestClient

from app import app


def test_health_endpoint():
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "MEMBRA KPI" in body["app"]


def test_homepage_loads():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert "Turn idle reality into measurable opportunity" in res.text


def test_api_docs_loads():
    client = TestClient(app)
    res = client.get("/api-docs")
    assert res.status_code == 200
    assert "POST /api/photo/analyze" in res.text
