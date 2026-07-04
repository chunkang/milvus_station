# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

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
    """Request body for POST /index.

    ``columns`` selects one or more text columns to embed (their per-row
    values are combined). ``column`` is kept for backward compatibility with
    single-field callers; ``columns`` takes precedence when both are given.
    """

    database: str
    table: str
    columns: list[str] | None = None
    column: str | None = None
    id_column: str | None = None


class FilterSpec(BaseModel):
    """A single numeric range constraint for a search.

    ``field`` names a numeric scalar field on the collection, ``op`` is one of
    ``lt``/``lte``/``eq``/``gte``/``gt``/``ne`` and ``value`` the comparison
    value. Validation (field must exist and be numeric, op must be allowed) is
    performed in :func:`app.vectors.search_collection`.
    """

    field: str
    op: str
    value: float


class SearchRequest(BaseModel):
    """Request body for POST /milvus/collections/{name}/search."""

    query: str
    top_k: int = 5
    filters: list[FilterSpec] | None = None


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
    """Embed one or more text columns and build a Milvus collection."""
    # Resolve the effective column list: `columns` wins, else the legacy
    # single `column`, else it's a bad request.
    selected = body.columns if body.columns else (
        [body.column] if body.column else []
    )
    if not selected:
        raise HTTPException(
            status_code=400, detail="at least one column is required"
        )
    return vectors.build_index(
        body.database, body.table, selected, body.id_column
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


@router.get("/milvus/collections/{name}/fields")
def get_milvus_collection_fields(name: str) -> dict[str, object]:
    """List a collection's numeric scalar fields available for filtering."""
    return vectors.list_filter_fields(name)


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
    filters = (
        [f.model_dump() for f in body.filters] if body.filters else None
    )
    return vectors.search_collection(
        name, body.query, body.top_k, filters=filters
    )


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
