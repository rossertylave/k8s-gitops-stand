from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_health_and_ready():
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_items():
    body = client.get("/items").json()
    assert len(body["items"]) == 5
    assert body["checksum"] is None


def test_items_with_work_is_deterministic():
    first = client.get("/items", params={"work": 1}).json()["checksum"]
    second = client.get("/items", params={"work": 1}).json()["checksum"]
    assert first == second and len(first) == 16


def test_work_out_of_range():
    assert client.get("/items", params={"work": 51}).status_code == 422


def test_item_not_found():
    assert client.get("/items/999").status_code == 404


def test_metrics_exposed():
    client.get("/items")
    assert "http_requests_total" in client.get("/metrics").text
