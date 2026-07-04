"""FastAPI application: health & data-console API.

SPEC-INFRA-001 / TASK-006 (health) + data-console browse/index endpoints.

The nginx reverse proxy maps ``/api/`` -> ``fastapi:8000/`` (stripping the
``/api`` prefix). To work whether or not the prefix is stripped, every
route is registered on a single :class:`APIRouter` that is mounted twice:
once at the root and once under ``/api``. So both ``/databases`` and
``/api/databases`` resolve to the same handler.

Out of scope (DEFERRED to SPEC-SEARCH-002): ``/api/embed`` and
``/api/search`` are intentionally NOT defined and therefore return 404.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import __version__, console, samples, vectors
from .health import gather_health

app = FastAPI(
    title="milvus_station backend",
    version=__version__,
    description="Health & data-console API (SPEC-INFRA-001, TASK-006).",
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


# --------------------------------------------------------------------------
# Data-console router (mounted at "" and "/api")
# --------------------------------------------------------------------------
router = APIRouter(tags=["console"])


class IndexRequest(BaseModel):
    """Request body for POST /index."""

    database: str
    table: str
    column: str
    id_column: str | None = None


class SearchRequest(BaseModel):
    """Request body for POST /milvus/collections/{name}/search."""

    query: str
    top_k: int = 5


@router.get("/databases")
def get_databases() -> dict[str, object]:
    """List non-system databases."""
    return {"databases": console.list_databases()}


@router.get("/databases/{db}/tables")
def get_tables(db: str) -> dict[str, object]:
    """List tables (with approx row counts) for a database."""
    return {"database": db, "tables": console.list_tables(db)}


@router.get("/databases/{db}/tables/{table}/columns")
def get_columns(db: str, table: str) -> dict[str, object]:
    """List columns (with embeddable flag) for a table."""
    return {
        "database": db,
        "table": table,
        "columns": console.list_columns(db, table),
    }


@router.get("/databases/{db}/tables/{table}/rows")
def get_table_rows(
    db: str,
    table: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(console.DEFAULT_PAGE_SIZE, ge=1),
) -> dict[str, object]:
    """Return a paginated slice of a table's rows."""
    return console.get_rows(db, table, page=page, page_size=page_size)


@router.post("/index")
def post_index(body: IndexRequest) -> dict[str, object]:
    """Embed a text column and build a Milvus collection for it."""
    return vectors.build_index(
        body.database, body.table, body.column, body.id_column
    )


@router.get("/milvus/collections")
def get_milvus_collections() -> dict[str, object]:
    """List Milvus collections with entity counts."""
    return vectors.list_collections()


@router.get("/milvus/collections/{name}")
def get_milvus_collection_rows(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(vectors.DEFAULT_PAGE_SIZE, ge=1),
) -> dict[str, object]:
    """Return a paginated slice of a Milvus collection's rows."""
    return vectors.query_collection(name, page=page, page_size=page_size)


@router.post("/milvus/collections/{name}/search")
def post_milvus_search(name: str, body: SearchRequest) -> dict[str, object]:
    """Semantic search over a Milvus collection.

    Prefers HTTP 400 for a missing/blank query; all other failures
    (Ollama or Milvus unreachable, model not pulled, missing collection)
    are returned as HTTP 200 with ``status: error`` by
    :func:`app.vectors.search_collection`.
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    return vectors.search_collection(name, body.query, body.top_k)


@router.post("/databases/{db}/samples/import")
def post_import_samples(db: str) -> dict[str, object]:
    """Create & seed the fixed sample tables in the application database.

    Restricted to the configured application database; any other ``db``
    returns HTTP 400. Idempotent (safe to call repeatedly).
    """
    return samples.import_samples(db)


# Mount twice so both /... and /api/... resolve (nginx may strip /api).
app.include_router(router)
app.include_router(router, prefix="/api")
