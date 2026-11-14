"""Сервіс catalog: каталог товарів демонстраційного застосунку shop.

Ендпоінт /items імітує обчислювальне навантаження (параметр work), щоб
під навантаженням зростало споживання CPU і спрацьовував HPA.
"""
import hashlib
import os
import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE = "catalog"
VERSION = os.getenv("APP_VERSION", "dev")
WORK_ITERATIONS = int(os.getenv("WORK_ITERATIONS", "20000"))
READY_FAIL = os.getenv("READY_FAIL", "false").lower() == "true"

ITEMS = {
    1: {"id": 1, "name": "Комутатор L2, 24 порти", "price": 5200.0},
    2: {"id": 2, "name": "Маршрутизатор SOHO", "price": 3100.0},
    3: {"id": 3, "name": "Патч-корд UTP cat.6, 2 м", "price": 85.0},
    4: {"id": 4, "name": "SFP-модуль 1G, 10 км", "price": 640.0},
    5: {"id": 5, "name": "Точка доступу Wi-Fi 6", "price": 4700.0},
}

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


def burn_cpu(units: int) -> str:
    """Детерміноване обчислювальне навантаження: units * WORK_ITERATIONS хешувань."""
    digest = b"seed"
    for _ in range(units * WORK_ITERATIONS):
        digest = hashlib.sha256(digest).digest()
    return digest.hex()[:16]


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


@app.get("/items")
def list_items(work: int = 0):
    if work < 0 or work > 50:
        raise HTTPException(status_code=422, detail="work must be in 0..50")
    checksum = burn_cpu(work) if work else None
    return {"items": list(ITEMS.values()), "version": VERSION, "checksum": checksum}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item
