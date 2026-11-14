"""Сервіс orders: приймає замовлення, перевіряє товар у сервісі catalog.

Стан зберігається в пам'яті процесу (обмеження стенда): сервіс навмисно
залишено без СКБД, щоб усі компоненти були stateless і масштабувались
горизонтально без додаткових припущень.
"""
import os
import time
from collections import deque
from itertools import count

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

SERVICE = "orders"
VERSION = os.getenv("APP_VERSION", "dev")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog")
READY_FAIL = os.getenv("READY_FAIL", "false").lower() == "true"
TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "2.0"))

ORDERS: deque = deque(maxlen=1000)
ORDER_ID = count(1)

REQUESTS = Counter(
    "http_requests_total", "Кількість HTTP-запитів", ["service", "method", "path", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "Тривалість обробки запиту", ["service", "path"]
)

app = FastAPI(title=SERVICE)


class OrderIn(BaseModel):
    item_id: int
    qty: int = Field(default=1, ge=1, le=100)


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


@app.post("/orders", status_code=201)
async def create_order(order: OrderIn):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{CATALOG_URL}/items/{order.item_id}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"catalog unavailable: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="item not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="catalog error")
    item = resp.json()
    record = {
        "id": next(ORDER_ID),
        "item_id": order.item_id,
        "qty": order.qty,
        "total": round(item["price"] * order.qty, 2),
    }
    ORDERS.append(record)
    return record


@app.get("/orders")
def list_orders():
    return {"count": len(ORDERS), "orders": list(ORDERS)[-20:], "version": VERSION}
