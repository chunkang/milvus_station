# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

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


class EmbeddingError(RuntimeError):
    """Base class for embedding failures carrying a user-facing message.

    ``str(exc)`` is safe to surface directly to the UI; ``build_index``
    forwards it verbatim as the ``message`` of an error payload.
    """


class EmbeddingModelNotAvailableError(EmbeddingError):
    """Raised when Ollama does not yet have the configured model pulled.

    Ollama answers ``/api/embeddings`` with HTTP 404 (or a body mentioning
    the model must be pulled) until the model is present. We do NOT pull
    from within the request; the compose ``ollama-init`` service handles
    that separately. Here we only produce a clear, actionable message.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(
            f"Embedding model '{model}' is not available yet. It is being "
            "prepared (pulled) on the server — please try again in a minute. "
            f"You can also run: docker compose exec ollama ollama pull {model}"
        )


class EmbeddingServiceUnreachableError(EmbeddingError):
    """Raised when Ollama cannot be reached at all (connection/timeout)."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model
        super().__init__("Embedding service (Ollama) is not reachable")


def sanitize_collection_name(db: str, table: str) -> str:
    """Build a Milvus-safe collection name from ``db`` and ``table``."""
    raw = f"{db}_{table}"
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", raw)
    if safe and safe[0].isdigit():
        safe = f"c_{safe}"
    return safe


def sanitize_field_name(name: str) -> str:
    """Build a Milvus-safe scalar field name from a column name.

    Milvus field names must be ``[0-9a-zA-Z_]`` and may not start with a digit.
    Used to derive the stored numeric field name from a source column so range
    filters (e.g. ``year >= 2000``) can reference it.
    """
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    if safe and safe[0].isdigit():
        safe = f"f_{safe}"
    return safe


def embed_text(text: str, settings: Settings | None = None) -> list[float]:
    """Return the embedding vector for ``text`` via Ollama.

    Uses ``httpx`` at module scope so tests can monkeypatch
    ``vectors.httpx.post``. Translates the two failure modes callers care
    about into typed :class:`EmbeddingError` subclasses whose messages are
    safe to show verbatim in the UI:

    * HTTP 404 (or a body indicating the model must be pulled) becomes
      :class:`EmbeddingModelNotAvailableError` — the configured model has
      not been pulled into Ollama yet.
    * Connection / timeout failures become
      :class:`EmbeddingServiceUnreachableError`.

    Any other error is re-raised unchanged so the generic error path can
    report it. The successful path is unchanged: it returns the vector.
    """
    settings = settings or get_settings()
    model = settings.ollama_model or "nomic-embed-text"
    url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"

    try:
        response = httpx.post(
            url,
            json={"model": model, "prompt": text},
            timeout=settings.probe_timeout_seconds + 30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Ollama returns 404 (and a "model ... not found" body) until the
        # model is pulled. Treat that specifically; do NOT auto-pull here.
        status = getattr(exc.response, "status_code", None)
        body = ""
        try:
            body = (exc.response.text or "").lower()
        except Exception:  # pragma: no cover - defensive, body is best-effort
            body = ""
        if status == 404 or "not found" in body or "pull" in body:
            raise EmbeddingModelNotAvailableError(model) from exc
        raise
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise EmbeddingServiceUnreachableError(model) from exc

    payload = response.json()
    return list(payload["embedding"])


def _clamp_page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page))
    page_size = int(page_size)
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    page_size = min(page_size, MAX_PAGE_SIZE)
    return page, page_size


def _combine_row_text(row: dict[str, Any], columns: list[str]) -> str:
    """Combine several column values of a row into one labelled text block.

    Each non-empty column contributes a ``"<column>: <value>"`` line, joined
    by newlines in the given column order. Empty/null values are skipped.
    Embedding this combined text lets a single vector capture multiple fields
    (e.g. a movie's title + overview + actors).
    """
    parts: list[str] = []
    for col in columns:
        value = row.get(col)
        if value is None or str(value).strip() == "":
            continue
        parts.append(f"{col}: {value}")
    return "\n".join(parts)


def build_index(
    database: str,
    table: str,
    columns: list[str] | str,
    id_column: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Embed one or more text columns and (re)build a Milvus collection.

    ``columns`` may be a list of column names (their per-row values are
    combined into one text before embedding) or a single string (backward
    compatible). Validation errors (unknown db/table/column) raise
    ``HTTPException`` (404). Ollama / Milvus failures are caught and returned
    as ``{"status": "error", ...}`` so the endpoint always answers 200.
    """
    settings = settings or get_settings()

    # Normalize to a de-duplicated, order-preserving list of column names.
    if isinstance(columns, str):
        columns = [columns]
    seen: set[str] = set()
    columns = [c for c in columns if c and not (c in seen or seen.add(c))]

    # --- identifier validation (raises 404 on mismatch, never interpolates raw) ---
    console.validate_database(database, settings)
    console.validate_table(database, table, settings)
    for col in columns:
        console.validate_column(database, table, col, settings)

    if id_column:
        console.validate_column(database, table, id_column, settings)
        pk_column = id_column
    else:
        pk_column = console.primary_key(database, table, settings)

    collection = sanitize_collection_name(database, table)

    if not columns:
        return {
            "status": "error",
            "collection": collection,
            "indexed": 0,
            "dim": 0,
            "columns": columns,
            "text_columns": [],
            "numeric_fields": [],
            "message": "at least one column is required",
        }

    # Split the selected columns by type. TEXT (and temporal) columns form the
    # embedded text; NUMERIC columns are stored as typed Milvus scalar fields so
    # search can filter on their magnitude (e.g. ``year >= 2000``). Type lookup
    # uses information_schema; unknown/omitted types default to text.
    col_types = console.column_types(database, table, settings)
    text_cols: list[str] = []
    num_cols: list[dict[str, str]] = []
    for col in columns:
        kind = console.numeric_kind(col_types.get(col, ""))
        if kind is None:
            text_cols.append(col)
        else:
            num_cols.append(
                {"orig": col, "name": sanitize_field_name(col), "kind": kind}
            )

    # Embedding text is built from the TEXT columns. If none were selected (all
    # numeric), fall back to combining every selected column so a vector still
    # exists to search against.
    embed_cols = text_cols if text_cols else columns

    numeric_summary = [
        {"name": nf["name"], "type": nf["kind"]} for nf in num_cols
    ]

    try:
        rows = console.read_pk_columns(
            database, table, pk_column, columns, MAX_INDEX_ROWS, settings
        )

        pks: list[int] = []
        vectors: list[list[float]] = []
        texts: list[str] = []
        num_values: dict[str, list[Any]] = {nf["orig"]: [] for nf in num_cols}
        dim: int | None = None

        for row in rows:
            text = _combine_row_text(row, embed_cols)
            if text.strip() == "":
                continue
            embedding = embed_text(text, settings)
            if dim is None:
                dim = len(embedding)
            pks.append(int(row["pk"]))
            vectors.append(embedding)
            texts.append(text[:TEXT_MAX_LENGTH])
            for nf in num_cols:
                raw = row.get(nf["orig"])
                if raw is None:
                    value: Any = 0
                elif nf["kind"] == "int":
                    value = int(raw)
                else:
                    value = float(raw)
                num_values[nf["orig"]].append(value)

        if dim is None:
            return {
                "status": "ok",
                "collection": collection,
                "indexed": 0,
                "dim": 0,
                "columns": columns,
                "text_columns": text_cols,
                "numeric_fields": numeric_summary,
                "message": "no non-empty text rows to index",
            }

        numeric_fields = [
            {
                "name": nf["name"],
                "kind": nf["kind"],
                "values": num_values[nf["orig"]],
            }
            for nf in num_cols
        ]
        _create_and_insert(
            collection, dim, pks, vectors, texts, numeric_fields, settings
        )

        return {
            "status": "ok",
            "collection": collection,
            "indexed": len(pks),
            "dim": dim,
            "columns": columns,
            "text_columns": text_cols,
            "numeric_fields": numeric_summary,
            "message": (
                f"indexed {len(pks)} rows into {collection} "
                f"from columns: {', '.join(columns)}"
            ),
        }
    except EmbeddingError as exc:  # model-not-pulled / Ollama unreachable
        # The message is crafted for end-users; forward it verbatim.
        return {
            "status": "error",
            "collection": collection,
            "indexed": 0,
            "dim": 0,
            "columns": columns,
            "text_columns": text_cols,
            "numeric_fields": [],
            "message": str(exc),
        }
    except Exception as exc:  # Milvus unreachable or any other failure
        return {
            "status": "error",
            "collection": collection,
            "indexed": 0,
            "dim": 0,
            "columns": columns,
            "text_columns": text_cols,
            "numeric_fields": [],
            "message": f"{type(exc).__name__}: {exc}",
        }


def _create_and_insert(
    collection: str,
    dim: int,
    pks: list[int],
    vectors: list[list[float]],
    texts: list[str],
    numeric_fields: list[dict[str, Any]],
    settings: Settings,
) -> None:
    """Create/recreate a Milvus collection and insert the vectors.

    ``numeric_fields`` is an ordered list of
    ``{"name": <sanitized>, "kind": "int"|"float", "values": [...]}`` describing
    the typed scalar fields to store alongside the embedding so search can
    filter on them. Each ``values`` list is aligned with ``pks``/``vectors``.

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
    for nf in numeric_fields:
        dtype = DataType.INT64 if nf["kind"] == "int" else DataType.DOUBLE
        fields.append(FieldSchema(name=nf["name"], dtype=dtype))
    schema = CollectionSchema(fields, description=f"embeddings for {collection}")
    coll = Collection(name=collection, schema=schema)

    # Order matters: insert + flush FIRST so the segment is sealed, THEN build
    # the index and load. Loading before the data is inserted/flushed leaves the
    # freshly inserted vectors unqueryable for a moment, so a browse immediately
    # after /index can read as empty. Doing it in this order guarantees the
    # collection is fully queryable by the time /index returns.
    #
    # Insert column order must mirror the schema field order:
    #   pks, vectors, texts, <numeric field 1 values>, <field 2 values>, ...
    data: list[Any] = [pks, vectors, texts]
    for nf in numeric_fields:
        data.append(nf["values"])
    coll.insert(data)
    coll.flush()
    coll.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        },
    )
    coll.load()


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


def _format_cell(value: Any) -> Any:
    """Format a Milvus field value for display.

    Long numeric vectors (e.g. a 768-dim embedding) are truncated to a short,
    readable preview — ``[0.1288, 0.2844, … (768 dims)]`` — rather than dumping
    every component into the table. All other values pass through
    :func:`app.console.jsonify` unchanged.
    """
    if (
        isinstance(value, (list, tuple))
        and len(value) > 12
        and all(isinstance(x, (int, float)) for x in value)
    ):
        head = ", ".join(f"{float(x):.4f}" for x in value[:8])
        return f"[{head}, … ({len(value)} dims)]"
    return console.jsonify(value)


# Reserved (non-filterable) field names common to every collection.
_RESERVED_FIELDS = frozenset({"pk", "embedding", "text"})

# Public filter operators mapped to their Milvus boolean-expression symbols.
FILTER_OPS: dict[str, str] = {
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "gte": ">=",
    "gt": ">",
    "ne": "!=",
}


def _numeric_schema_fields(coll: Any) -> dict[str, str]:
    """Map a collection's numeric scalar fields to ``"int"`` / ``"float"``.

    Reads ``coll.schema.fields`` and returns ``{field_name: kind}`` for the
    typed scalar fields (INT64 -> ``"int"``, DOUBLE -> ``"float"``), excluding
    the reserved ``pk`` / ``embedding`` / ``text`` fields. ``pymilvus`` is
    imported lazily so tests can supply a fake ``DataType``.
    """
    from pymilvus import DataType  # lazy import

    result: dict[str, str] = {}
    for field in getattr(coll.schema, "fields", []):
        if field.name in _RESERVED_FIELDS:
            continue
        if field.dtype == DataType.INT64:
            result[field.name] = "int"
        elif field.dtype == DataType.DOUBLE:
            result[field.name] = "float"
    return result


def list_filter_fields(
    name: str, settings: Settings | None = None
) -> dict[str, Any]:
    """List a collection's numeric scalar fields available for range filtering.

    Returns ``{"collection": name, "fields": [{"name", "type"}]}`` where
    ``type`` is ``"int"`` (INT64) or ``"float"`` (DOUBLE). The reserved
    ``pk`` / ``embedding`` / ``text`` fields are excluded. If Milvus is
    unreachable or the collection is missing, returns
    ``{"collection": name, "fields": [], "status": "unreachable"}``.
    """
    settings = settings or get_settings()
    try:
        from pymilvus import Collection, connections, utility  # lazy import

        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=str(settings.milvus_port),
        )
        if not utility.has_collection(name):
            return {"collection": name, "fields": [], "status": "unreachable"}

        coll = Collection(name)
        fields = [
            {"name": fname, "type": kind}
            for fname, kind in _numeric_schema_fields(coll).items()
        ]
        return {"collection": name, "fields": fields}
    except Exception:
        return {"collection": name, "fields": [], "status": "unreachable"}


DEFAULT_TOP_K = 5
MAX_TOP_K = 50


def _clamp_top_k(top_k: int) -> int:
    """Coerce ``top_k`` to an int in the inclusive range 1..MAX_TOP_K."""
    try:
        value = int(top_k)
    except (TypeError, ValueError):
        return DEFAULT_TOP_K
    if value < 1:
        return DEFAULT_TOP_K
    return min(value, MAX_TOP_K)


def search_collection(
    name: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    filters: list[dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Semantic search over a Milvus collection for a natural-language query.

    The query text is embedded via :func:`embed_text` (Ollama) and the
    resulting vector is searched against the collection's ``embedding``
    field using COSINE similarity. Results are returned best-first.

    ``filters`` is an optional list of ``{"field", "op", "value"}`` numeric
    range constraints. Each ``field`` must be one of the collection's numeric
    scalar fields (INT64/DOUBLE) and each ``op`` one of
    :data:`FILTER_OPS` (``lt``/``lte``/``eq``/``gte``/``gt``/``ne``); the value
    is coerced to the field's kind (int/float). The filters are combined with
    ``and`` into a Milvus boolean expression applied to the search.

    Like the rest of this module, every failure is converted into a
    structured ``{"status": "error", ...}`` payload so the route always
    answers HTTP 200 rather than 500:

    * empty / whitespace-only query -> ``"query is required"``
    * unknown filter field / operator -> a clear message
    * model-not-pulled / Ollama unreachable -> the :class:`EmbeddingError`
      message forwarded verbatim (same friendly text as ``build_index``)
    * Milvus unreachable / missing collection -> a clear message
    """
    settings = settings or get_settings()
    top_k = _clamp_top_k(top_k)
    base = {"collection": name, "query": query, "top_k": top_k}

    if not query or not query.strip():
        return {**base, "results": [], "status": "error", "message": "query is required"}

    # --- embed the query (typed failures -> forwarded message) ---
    try:
        query_vector = embed_text(query, settings)
    except EmbeddingError as exc:
        return {**base, "results": [], "status": "error", "message": str(exc)}

    # --- search Milvus (any failure -> friendly error, never a 500) ---
    try:
        from pymilvus import Collection, connections, utility  # lazy import

        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=str(settings.milvus_port),
        )

        if not utility.has_collection(name):
            return {
                **base,
                "results": [],
                "status": "error",
                "message": f"collection '{name}' not found",
            }

        coll = Collection(name)

        # Build the optional filter expression from the collection's own numeric
        # scalar fields. Every field/op is validated against an allow-list; the
        # value is coerced to the field's kind so the expression is well-typed
        # (e.g. ``year >= 2000`` rather than ``year >= 2000.0``).
        expr: str | None = None
        if filters:
            numeric_fields = _numeric_schema_fields(coll)
            parts: list[str] = []
            for spec in filters:
                field = spec.get("field")
                op = spec.get("op")
                value = spec.get("value")
                if field not in numeric_fields:
                    return {
                        **base,
                        "results": [],
                        "status": "error",
                        "message": f"unknown filter field: {field}",
                    }
                if op not in FILTER_OPS:
                    return {
                        **base,
                        "results": [],
                        "status": "error",
                        "message": f"unknown filter op: {op}",
                    }
                if numeric_fields[field] == "int":
                    coerced: Any = int(value)
                else:
                    coerced = float(value)
                parts.append(f"{field} {FILTER_OPS[op]} {coerced}")
            expr = " and ".join(parts)

        coll.load()

        search_result = coll.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=top_k,
            expr=expr,
            output_fields=["pk", "text"],
        )

        hits = search_result[0] if search_result else []
        results: list[dict[str, Any]] = []
        for hit in hits:
            entity = getattr(hit, "entity", None)
            pk = getattr(hit, "id", None)
            if pk is None and entity is not None:
                pk = entity.get("pk")
            text = entity.get("text") if entity is not None else None
            score = getattr(hit, "distance", None)
            if score is None:
                score = getattr(hit, "score", 0.0)
            results.append(
                {"pk": int(pk), "text": text, "score": float(score)}
            )

        out = {**base, "results": results, "status": "ok"}
        if filters:
            out["filters"] = filters
        return out
    except Exception as exc:  # Milvus unreachable or any other failure
        return {
            **base,
            "results": [],
            "status": "error",
            "message": f"{type(exc).__name__}: {exc}",
        }


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

        # Output ALL fields, including the embedding vector, so users can
        # actually inspect the stored vectors in the browser. Long vectors are
        # truncated to a readable preview (see ``_format_cell``) to keep the
        # payload and the table sane.
        field_names: list[str] = [f.name for f in coll.schema.fields]

        rows = coll.query(
            expr="pk >= 0",
            offset=offset,
            limit=page_size,
            output_fields=field_names,
        )
        clean_rows = [
            {k: _format_cell(v) for k, v in row.items()} for row in rows
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
