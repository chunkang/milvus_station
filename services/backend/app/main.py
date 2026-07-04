"""FastAPI application: health & status service.

SPEC-INFRA-001 / TASK-006.

Exposes health endpoints only. The nginx reverse proxy may or may not
strip the /api prefix, so both /health and /api/health are exposed.

Out of scope (DEFERRED to SPEC-SEARCH-002): /api/embed and /api/search
are intentionally NOT defined here and therefore return 404.
"""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .health import gather_health

app = FastAPI(
    title="milvus_station backend",
    version=__version__,
    description="Health & status service (SPEC-INFRA-001, TASK-006).",
)


async def _health_payload() -> dict[str, object]:
    """Aggregate component health into the response body."""
    return await gather_health()


@app.get("/health")
async def health() -> dict[str, object]:
    """Health endpoint (unprefixed path)."""
    return await _health_payload()


@app.get("/api/health")
async def api_health() -> dict[str, object]:
    """Health endpoint (api-prefixed path, for proxies that keep /api)."""
    return await _health_payload()
