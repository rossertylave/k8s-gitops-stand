from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_and_version():
    assert client.get("/healthz").status_code == 200
    assert client.get("/version").json()["service"] == "gateway"


def test_upstream_unavailable_returns_503(monkeypatch):
    monkeypatch.setattr("app.CATALOG_URL", "http://127.0.0.1:9")
    assert client.get("/api/items").status_code == 503
