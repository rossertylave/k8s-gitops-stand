"""Сервіс gateway: єдина точка входу (API gateway) застосунку shop.

Проксіює запити до сервісів catalog та orders за їхніми DNS-іменами
всередині кластера (Service discovery засобами Kubernetes).
"""
import os
import time

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE = "gateway"
VERSION = os.getenv("APP_VERSION", "dev")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog")
ORDERS_URL = os.getenv("ORDERS_URL", "http://orders")
READY_FAIL = os.getenv("READY_FAIL", "false").lower() == "true"
TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "5.0"))

REQUESTS = Counter(
    "http_requests_total", "Кількість HTTP-запитів", ["service", "method", "path", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "Тривалість обробки запиту", ["service", "path"]
)

app = FastAPI(title=SERVICE)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    if path not in ("/metrics", "/healthz", "/readyz"):
        REQUESTS.labels(SERVICE, request.method, path, str(response.status_code)).inc()
        LATENCY.labels(SERVICE, path).observe(time.perf_counter() - start)
    return response


async def forward(method: str, url: str, **kwargs) -> Response:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            upstream = await client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"upstream unavailable: {exc}") from exc
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    if READY_FAIL:
        raise HTTPException(status_code=503, detail="not ready (READY_FAIL=true)")
    return {"status": "ready"}


@app.get("/version")
def version():
    return {"service": SERVICE, "version": VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/items")
async def api_items(work: int = 0):
    return await forward("GET", f"{CATALOG_URL}/items", params={"work": work})


@app.get("/api/items/{item_id}")
async def api_item(item_id: int):
    return await forward("GET", f"{CATALOG_URL}/items/{item_id}")


@app.post("/api/orders")
async def api_create_order(request: Request):
    body = await request.body()
    return await forward(
        "POST", f"{ORDERS_URL}/orders", content=body, headers={"content-type": "application/json"}
    )


@app.get("/api/orders")
async def api_orders():
    return await forward("GET", f"{ORDERS_URL}/orders")


@app.get("/api/versions")
async def api_versions():
    """Версії всіх сервісів: використовується скриптами експериментів."""
    result = {SERVICE: VERSION}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for name, url in (("catalog", CATALOG_URL), ("orders", ORDERS_URL)):
            try:
                result[name] = (await client.get(f"{url}/version")).json()["version"]
            except (httpx.HTTPError, KeyError, ValueError):
                result[name] = "unavailable"
    return result
