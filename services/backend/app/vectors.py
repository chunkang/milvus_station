"""Embedding + Milvus vector indexing / browsing.

Two external systems are involved:

* Ollama  -- produces embedding vectors via its HTTP ``/api/embeddings``
             endpoint (called with ``httpx``).
* Milvus  -- stores the vectors; accessed through ``pymilvus`` which is
             *lazily imported inside each function* so unit tests can
             inject a fake module and the package is never required when
             mocked.

All outward calls are best-effort: if Ollama or Milvus is unreachable the
functions return a structured ``status`` payload (HTTP 200 at the route
layer) rather than raising, so the data console never crashes when its
backing services are down. Identifier validation for db/table/column is
delegated to :mod:`app.console`, which enforces the information_schema
allow-list before any live query is built.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from . import console
from .config import Settings, get_settings

# Upper bound on rows pulled from a table for a single index build.
MAX_INDEX_ROWS = 1000
# Milvus VARCHAR fields are length-bounded; truncate stored text to fit.
TEXT_MAX_LENGTH = 4096

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def sanitize_collection_name(db: str, table: str) -> str:
    """Build a Milvus-safe collection name from ``db`` and ``table``."""
    raw = f"{db}_{table}"
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", raw)
    if safe and safe[0].isdigit():
        safe = f"c_{safe}"
    return safe


def embed_text(text: str, settings: Settings | None = None) -> list[float]:
    """Return the embedding vector for ``text`` via Ollama.

    Uses ``httpx`` at module scope so tests can monkeypatch
    ``vectors.httpx.post``. Raises on transport / HTTP errors so callers
    can convert failures into a structured error payload.
    """
    settings = settings or get_settings()
    model = settings.ollama_model or "nomic-embed-text"
    url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"

    response = httpx.post(
        url,
        json={"model": model, "prompt": text},
        timeout=settings.probe_timeout_seconds + 30,
    )
    response.raise_for_status()
    payload = response.json()
    return list(payload["embedding"])


def _clamp_page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page))
    page_size = int(page_size)
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    page_size = min(page_size, MAX_PAGE_SIZE)
    return page, page_size


def build_index(
    database: str,
    table: str,
    column: str,
    id_column: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Embed a text column and (re)build a Milvus collection for it.

    Validation errors (unknown db/table/column) raise ``HTTPException``
    (404) and propagate. Ollama / Milvus failures are caught and returned
    as ``{"status": "error", ...}`` so the endpoint always answers 200.
    """
    settings = settings or get_settings()

    # --- identifier validation (raises 404 on mismatch, never interpolates raw) ---
    console.validate_database(database, settings)
    console.validate_table(database, table, settings)
    console.validate_column(database, table, column, settings)

    if id_column:
        console.validate_column(database, table, id_column, settings)
        pk_column = id_column
    else:
        pk_column = console.primary_key(database, table, settings)

    collection = sanitize_collection_name(database, table)

    try:
        rows = console.read_pk_text(
            database, table, pk_column, column, MAX_INDEX_ROWS, settings
        )

        pks: list[int] = []
        vectors: list[list[float]] = []
        texts: list[str] = []
        dim: int | None = None

        for row in rows:
            text = row.get("text")
            if text is None or str(text).strip() == "":
                continue
            embedding = embed_text(str(text), settings)
            if dim is None:
                dim = len(embedding)
            pks.append(int(row["pk"]))
            vectors.append(embedding)
            texts.append(str(text)[:TEXT_MAX_LENGTH])

        if dim is None:
            return {
                "status": "ok",
                "collection": collection,
                "indexed": 0,
                "dim": 0,
                "message": "no non-empty text rows to index",
            }

        _create_and_insert(collection, dim, pks, vectors, texts, settings)

        return {
            "status": "ok",
            "collection": collection,
            "indexed": len(pks),
            "dim": dim,
            "message": f"indexed {len(pks)} rows into {collection}",
        }
    except Exception as exc:  # Ollama / Milvus unreachable or failed
        return {
            "status": "error",
            "collection": collection,
            "indexed": 0,
            "dim": 0,
            "message": f"{type(exc).__name__}: {exc}",
        }


def _create_and_insert(
    collection: str,
    dim: int,
    pks: list[int],
    vectors: list[list[float]],
    texts: list[str],
    settings: Settings,
) -> None:
    """Create/recreate a Milvus collection and insert the vectors.

    ``pymilvus`` is imported lazily so tests can supply a fake module.
    """
    from pymilvus import (  # lazy import
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )

    connections.connect(
        alias="default",
        host=settings.milvus_host,
        port=str(settings.milvus_port),
    )

    if utility.has_collection(collection):
        utility.drop_collection(collection)

    fields = [
        FieldSchema(
            name="pk", dtype=DataType.INT64, is_primary=True, auto_id=False
        ),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(
            name="text", dtype=DataType.VARCHAR, max_length=TEXT_MAX_LENGTH + 1
        ),
    ]
    schema = CollectionSchema(fields, description=f"embeddings for {collection}")
    coll = Collection(name=collection, schema=schema)

    coll.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        },
    )
    coll.load()
    coll.insert([pks, vectors, texts])
    coll.flush()


def list_collections(settings: Settings | None = None) -> dict[str, Any]:
    """List Milvus collections with entity counts, or a degraded payload."""
    settings = settings or get_settings()
    try:
        from pymilvus import Collection, connections, utility  # lazy import

        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=str(settings.milvus_port),
        )
        names = list(utility.list_collections())
        collections = []
        for name in names:
            try:
                count = int(Collection(name).num_entities)
            except Exception:
                count = 0
            collections.append({"name": name, "count": count})
        return {"collections": collections}
    except Exception:
        return {"collections": [], "status": "unreachable"}


def query_collection(
    name: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return a paginated slice of a Milvus collection's non-vector fields."""
    settings = settings or get_settings()
    page, page_size = _clamp_page(page, page_size)
    offset = (page - 1) * page_size

    try:
        from pymilvus import Collection, connections  # lazy import

        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=str(settings.milvus_port),
        )
        coll = Collection(name)
        coll.load()
        total = int(coll.num_entities)

        # Non-vector output fields only (skip FLOAT_VECTOR / BINARY_VECTOR).
        field_names: list[str] = []
        for field in coll.schema.fields:
            dtype_name = str(getattr(field, "dtype", "")).upper()
            if "VECTOR" in dtype_name:
                continue
            field_names.append(field.name)

        rows = coll.query(
            expr="pk >= 0",
            offset=offset,
            limit=page_size,
            output_fields=field_names,
        )
        clean_rows = [
            {k: console.jsonify(v) for k, v in row.items()} for row in rows
        ]
        return {
            "collection": name,
            "page": page,
            "page_size": page_size,
            "total": total,
            "fields": field_names,
            "rows": clean_rows,
        }
    except Exception:
        return {
            "collection": name,
            "page": page,
            "page_size": page_size,
            "total": 0,
            "fields": [],
            "rows": [],
            "status": "unreachable",
        }
