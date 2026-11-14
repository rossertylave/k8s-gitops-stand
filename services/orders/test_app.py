import httpx
from fastapi.testclient import TestClient

import app as orders_app

client = TestClient(orders_app.app)


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response=None, error=None):
        self._response, self._error = response, error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        if self._error:
            raise self._error
        return self._response


def patch_catalog(monkeypatch, **kwargs):
    monkeypatch.setattr(orders_app.httpx, "AsyncClient", lambda **_: FakeClient(**kwargs))


def test_create_order(monkeypatch):
    patch_catalog(monkeypatch, response=FakeResponse(200, {"id": 3, "price": 85.0}))
    resp = client.post("/orders", json={"item_id": 3, "qty": 4})
    assert resp.status_code == 201
    assert resp.json()["total"] == 340.0


def test_unknown_item(monkeypatch):
    patch_catalog(monkeypatch, response=FakeResponse(404))
    assert client.post("/orders", json={"item_id": 99}).status_code == 404


def test_catalog_down(monkeypatch):
    patch_catalog(monkeypatch, error=httpx.ConnectError("down"))
    assert client.post("/orders", json={"item_id": 1}).status_code == 503


def test_invalid_qty():
    assert client.post("/orders", json={"item_id": 1, "qty": 0}).status_code == 422
