# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

"""Tests for the embedding / Milvus vector endpoints.

Ollama is mocked at the ``httpx`` layer and Milvus via a fake ``pymilvus``
module injected into ``sys.modules`` (the real package is never required).
Identifier validation is stubbed so these tests focus on the embed +
Milvus orchestration and the graceful-degradation contract.
"""

from __future__ import annotations

import sys
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from app import console, vectors
from app.main import app


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def _model_not_found_post(url, json=None, timeout=None):
    """Simulate Ollama returning HTTP 404 for an un-pulled model.

    Builds a real ``httpx.Response`` so ``raise_for_status`` raises a
    genuine ``httpx.HTTPStatusError`` exactly like the live client would.
    """
    request = httpx.Request("POST", url)
    return httpx.Response(
        status_code=404,
        request=request,
        json={"error": 'model "nomic-embed-text" not found, try pulling it first'},
    )


class _FakeEntity:
    """Minimal stand-in for a pymilvus hit entity (``.get(field)``)."""

    def __init__(self, fields):
        self._fields = fields

    def get(self, key, default=None):
        return self._fields.get(key, default)


class _FakeHit:
    """Minimal stand-in for a pymilvus search hit.

    Exposes ``.id`` and ``.distance`` plus an ``.entity`` with ``.get``,
    mirroring the attributes ``search_collection`` reads.
    """

    def __init__(self, pk, text, score):
        self.id = pk
        self.distance = score
        self.entity = _FakeEntity({"pk": pk, "text": text})


def _make_fake_pymilvus(
    record, connect_error=False, extra_fields=None, schema_description=""
):
    """Build a fake ``pymilvus`` module.

    ``extra_fields`` optionally augments the DEFAULT collection schema with
    numeric scalar fields — a list of ``(name, dtype)`` tuples (dtype being one
    of the ``DataType`` string constants, e.g. ``"INT64"`` / ``"DOUBLE"``) — so
    tests that open ``Collection(name)`` (search / list_filter_fields) see
    filterable fields without first running ``build_index``.

    ``schema_description`` sets the ``description`` on the DEFAULT schema exposed
    by a freshly constructed ``Collection(name)`` (no explicit schema). Search
    hydration reads this to discover the source ``{database, table, pk_column}``;
    the default empty string mirrors an older collection with no such metadata,
    so hydration is skipped and existing tests are unaffected.
    """
    mod = types.ModuleType("pymilvus")

    class DataType:
        INT64 = "INT64"
        DOUBLE = "DOUBLE"
        FLOAT_VECTOR = "FLOAT_VECTOR"
        VARCHAR = "VARCHAR"

    class FieldSchema:
        def __init__(self, name, dtype, **kw):
            self.name = name
            self.dtype = dtype
            self.kw = kw

    class CollectionSchema:
        def __init__(self, fields, description=""):
            self.fields = fields
            self.description = description

    class _Schema:
        def __init__(self, fields, description=""):
            self.fields = fields
            self.description = description

    _DEFAULT_FIELDS = [
        FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=3),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=100),
    ]
    for _fname, _fdtype in (extra_fields or []):
        _DEFAULT_FIELDS.append(FieldSchema(name=_fname, dtype=_fdtype))

    class Collection:
        def __init__(self, name, schema=None):
            self.name = name
            if schema is not None:
                self.schema = schema
                # Expose the created schema's fields so build_index tests can
                # assert numeric scalar fields were declared.
                record["schema_fields"] = [
                    (f.name, f.dtype) for f in schema.fields
                ]
            else:
                self.schema = _Schema(
                    list(_DEFAULT_FIELDS), description=schema_description
                )

        def create_index(self, field_name, index_params):
            record["index_params"] = index_params

        def load(self):
            record["loaded"] = True

        def insert(self, data):
            record["inserted"] = data

        def flush(self):
            record["flushed"] = True

        @property
        def num_entities(self):
            return 2

        def query(self, expr, offset=0, limit=10, output_fields=None):
            record["query"] = {
                "expr": expr,
                "offset": offset,
                "limit": limit,
                "output_fields": output_fields,
            }
            # A realistic row now includes the embedding vector so the browse
            # view can surface it (truncated to a preview by the endpoint).
            return [{"pk": 1, "embedding": [0.1] * 768, "text": "hello"}]

        def search(
            self, data, anns_field, param, limit, expr=None, output_fields=None
        ):
            record["search"] = {
                "data": data,
                "anns_field": anns_field,
                "param": param,
                "limit": limit,
                "expr": expr,
                "output_fields": output_fields,
            }
            # Two hits, already ranked best-first (higher COSINE = closer).
            return [
                [
                    _FakeHit(pk=3, text="how to reset your password", score=0.91),
                    _FakeHit(pk=1, text="account settings overview", score=0.72),
                ]
            ]

    class connections:
        @staticmethod
        def connect(**kw):
            if connect_error:
                raise ConnectionError("milvus unreachable")
            record["connected"] = kw

    class utility:
        @staticmethod
        def has_collection(name):
            return True

        @staticmethod
        def drop_collection(name):
            record["dropped"] = name

        @staticmethod
        def list_collections():
            return ["shop_users"]

    mod.DataType = DataType
    mod.FieldSchema = FieldSchema
    mod.CollectionSchema = CollectionSchema
    mod.Collection = Collection
    mod.connections = connections
    mod.utility = utility
    return mod


@pytest.fixture()
def stub_validation(monkeypatch):
    """Bypass information_schema validation with permissive stubs."""
    monkeypatch.setattr(console, "validate_database", lambda db, settings=None: db)
    monkeypatch.setattr(
        console, "validate_table", lambda db, table, settings=None: table
    )
    monkeypatch.setattr(
        console, "validate_column", lambda db, table, col, settings=None: col
    )
    monkeypatch.setattr(console, "primary_key", lambda db, table, settings=None: "id")
    # Default: no numeric columns, so every selected column is treated as text
    # (preserving pre-numeric-filter behaviour). Numeric tests override this.
    monkeypatch.setattr(
        console, "column_types", lambda db, table, settings=None: {}
    )
    monkeypatch.setattr(
        console,
        "read_pk_text",
        lambda db, table, pk, col, limit=1000, settings=None: [
            {"pk": 1, "text": "hello"},
            {"pk": 2, "text": ""},  # empty -> skipped
            {"pk": 3, "text": "world"},
        ],
    )

    def _fake_read_pk_columns(db, table, pk, columns, limit=1000, settings=None):
        # Three canned rows; each requested column gets the same base value so
        # single-column tests behave exactly as before (row 2 is empty ->
        # skipped). Multi-column tests override this per test as needed.
        canned = [(1, "hello"), (2, ""), (3, "world")]
        rows = []
        for pk_val, value in canned:
            row = {"pk": pk_val}
            for col in columns:
                row[col] = value
            rows.append(row)
        return rows

    monkeypatch.setattr(console, "read_pk_columns", _fake_read_pk_columns)


@pytest.fixture()
def ok_ollama(monkeypatch):
    monkeypatch.setattr(
        vectors.httpx,
        "post",
        lambda url, json=None, timeout=None: _FakeResponse(
            {"embedding": [0.1, 0.2, 0.3]}
        ),
    )


@pytest.fixture()
def client():
    return TestClient(app)


# --------------------------------------------------------------------------
# build_index
# --------------------------------------------------------------------------
def test_index_success_returns_indexed_and_dim(
    monkeypatch, stub_validation, ok_ollama
):
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))

    result = vectors.build_index("shop", "users", "bio")

    assert result["status"] == "ok"
    assert result["indexed"] == 2  # two non-empty texts
    assert result["dim"] == 3
    assert result["collection"] == "shop_users"
    # IVF_FLAT + COSINE index was built and vectors inserted.
    assert record["index_params"]["index_type"] == "IVF_FLAT"
    assert record["index_params"]["metric_type"] == "COSINE"
    assert record["inserted"][0] == [1, 3]  # pks (empty row skipped)


def test_index_multi_column_combines_fields(monkeypatch, stub_validation):
    """Selecting several columns combines their per-row values into one
    labelled text (``col: value`` lines) before embedding."""
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))

    # Rows with DISTINCT values per column so we can assert the combination.
    monkeypatch.setattr(
        console,
        "read_pk_columns",
        lambda db, table, pk, columns, limit=1000, settings=None: [
            {"pk": 1, "title": "Inception", "overview": "A heist in dreams"},
        ],
    )
    # Capture the exact text handed to embed_text.
    seen: list[str] = []

    def _capture(text, settings=None):
        seen.append(text)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(vectors, "embed_text", _capture)

    result = vectors.build_index("shop", "films", ["title", "overview"])

    assert result["status"] == "ok"
    assert result["indexed"] == 1
    assert result["columns"] == ["title", "overview"]
    # The combined text contains both fields, labelled, in order, newline-joined.
    assert seen == ["title: Inception\noverview: A heist in dreams"]


def test_index_endpoint_accepts_columns_list(
    monkeypatch, stub_validation, ok_ollama, client
):
    """POST /index accepts a ``columns`` list and indexes successfully."""
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))
    resp = client.post(
        "/index",
        json={"database": "shop", "table": "users", "columns": ["bio", "title"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["columns"] == ["bio", "title"]


def test_index_endpoint_requires_at_least_one_column(client):
    """POST /index with neither columns nor column is a 400."""
    resp = client.post("/index", json={"database": "shop", "table": "users"})
    assert resp.status_code == 400


def test_index_ollama_unreachable_returns_error(
    monkeypatch, stub_validation
):
    def boom(url, json=None, timeout=None):
        raise httpx.ConnectError("ollama down")

    monkeypatch.setattr(vectors.httpx, "post", boom)
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))

    result = vectors.build_index("shop", "users", "bio")
    assert result["status"] == "error"
    assert "message" in result


def test_index_model_not_pulled_returns_graceful_error(
    monkeypatch, stub_validation
):
    """A 404 from Ollama (model not pulled) must not raise and must yield a
    clear, actionable message mentioning the model name and guidance."""
    monkeypatch.setattr(vectors.httpx, "post", _model_not_found_post)
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))

    # Must not raise despite httpx.HTTPStatusError under the hood.
    result = vectors.build_index("shop", "users", "bio")

    assert result["status"] == "error"
    assert result["indexed"] == 0
    message = result["message"]
    assert "nomic-embed-text" in message  # actual configured model name
    assert "try again" in message.lower()
    assert "pull" in message.lower()


def test_index_endpoint_model_not_pulled_returns_200_error(
    monkeypatch, stub_validation, client
):
    """POST /index returns HTTP 200 with status:error and pull guidance when
    the embedding model is not available in Ollama yet."""
    monkeypatch.setattr(vectors.httpx, "post", _model_not_found_post)
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))

    resp = client.post(
        "/index", json={"database": "shop", "table": "users", "column": "bio"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "nomic-embed-text" in body["message"]
    assert "try again" in body["message"].lower()
    assert "pull" in body["message"].lower()


def test_index_milvus_unreachable_returns_error(
    monkeypatch, stub_validation, ok_ollama
):
    monkeypatch.setitem(
        sys.modules, "pymilvus", _make_fake_pymilvus({}, connect_error=True)
    )

    result = vectors.build_index("shop", "users", "bio")
    assert result["status"] == "error"


def test_index_endpoint_success(monkeypatch, stub_validation, ok_ollama, client):
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))
    resp = client.post(
        "/index", json={"database": "shop", "table": "users", "column": "bio"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dim"] == 3


# --------------------------------------------------------------------------
# Milvus collection browsing
# --------------------------------------------------------------------------
def test_collections_unreachable_when_milvus_down(client):
    # No fake pymilvus injected and the real package is not installed, so the
    # lazy import fails -> graceful "unreachable" payload, HTTP 200.
    sys.modules.pop("pymilvus", None)
    resp = client.get("/milvus/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collections"] == []
    assert body["status"] == "unreachable"


def test_collections_success(monkeypatch, client):
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))
    resp = client.get("/api/milvus/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collections"] == [{"name": "shop_users", "count": 2}]
    assert "status" not in body


def test_collection_rows_unreachable(client):
    sys.modules.pop("pymilvus", None)
    resp = client.get("/milvus/collections/shop_users?page=2&page_size=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"] == []
    assert body["fields"] == []
    assert body["total"] == 0
    assert body["status"] == "unreachable"


def test_collection_rows_success(monkeypatch, client):
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))
    resp = client.get("/milvus/collections/shop_users?page=1&page_size=25")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "shop_users"
    assert body["total"] == 2
    # embedding (FLOAT_VECTOR) is now INCLUDED so users can inspect vectors,
    # and the endpoint requested it as an output field.
    assert body["fields"] == ["pk", "embedding", "text"]
    assert "embedding" in record["query"]["output_fields"]
    row = body["rows"][0]
    assert row["pk"] == 1
    assert row["text"] == "hello"
    # the 768-dim vector is truncated to a readable preview, not dumped whole
    assert "768 dims" in row["embedding"]
    assert row["embedding"].startswith("[0.1000, 0.1000")


# --------------------------------------------------------------------------
# Semantic search
# --------------------------------------------------------------------------
def test_search_success_returns_ranked_results(monkeypatch, ok_ollama, client):
    """POST /search embeds the query and returns ranked {pk,text,score}."""
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))

    resp = client.post(
        "/milvus/collections/milvus_station_faqs/search",
        json={"query": "reset password", "top_k": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["collection"] == "milvus_station_faqs"
    assert body["query"] == "reset password"
    assert body["top_k"] == 3

    results = body["results"]
    assert isinstance(results, list)
    assert all(set(r) == {"pk", "text", "score"} for r in results)
    # ranked best-first, exactly as returned by the (fake) search
    assert [r["pk"] for r in results] == [3, 1]
    assert [r["score"] for r in results] == [0.91, 0.72]
    assert results[0]["text"] == "how to reset your password"

    # searched with COSINE metric and the requested limit
    assert record["search"]["param"]["metric_type"] == "COSINE"
    assert record["search"]["limit"] == 3
    assert record["search"]["anns_field"] == "embedding"


def test_search_top_k_clamped_to_50(monkeypatch, ok_ollama, client):
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))
    resp = client.post(
        "/milvus/collections/milvus_station_faqs/search",
        json={"query": "anything", "top_k": 999},
    )
    assert resp.status_code == 200
    assert resp.json()["top_k"] == 50
    assert record["search"]["limit"] == 50


def test_search_model_not_pulled_returns_200_error(monkeypatch, client):
    """A 404 from Ollama (model not pulled) -> HTTP 200 status:error with a
    clear message mentioning the model and pull guidance."""
    monkeypatch.setattr(vectors.httpx, "post", _model_not_found_post)
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus({}))

    resp = client.post(
        "/milvus/collections/milvus_station_faqs/search",
        json={"query": "reset password", "top_k": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["results"] == []
    assert "nomic-embed-text" in body["message"]
    assert "pull" in body["message"].lower()


def test_search_empty_query_returns_400(client):
    """A blank query is a client error -> HTTP 400."""
    resp = client.post(
        "/milvus/collections/milvus_station_faqs/search",
        json={"query": "   ", "top_k": 3},
    )
    assert resp.status_code == 400


def test_search_missing_collection_returns_error(monkeypatch, ok_ollama, client):
    """When the collection does not exist -> status:error, HTTP 200."""
    record = {}
    fake = _make_fake_pymilvus(record)
    fake.utility.has_collection = staticmethod(lambda name: False)
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.post(
        "/milvus/collections/does_not_exist/search",
        json={"query": "hello"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["results"] == []
    assert "not found" in body["message"].lower()
    # default top_k applied when omitted
    assert body["top_k"] == 5


def test_search_milvus_unreachable_returns_error(monkeypatch, ok_ollama, client):
    monkeypatch.setitem(
        sys.modules, "pymilvus", _make_fake_pymilvus({}, connect_error=True)
    )
    resp = client.post(
        "/milvus/collections/milvus_station_faqs/search",
        json={"query": "hello"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["results"] == []


# --------------------------------------------------------------------------
# Numeric range filtering
# --------------------------------------------------------------------------
def test_index_numeric_column_stored_as_scalar_field(
    monkeypatch, stub_validation, ok_ollama
):
    """A selected NUMERIC column becomes a typed Milvus scalar field.

    The embedded text is built from the TEXT column only; the numeric value is
    inserted as its own aligned column and reported in ``numeric_fields``.
    """
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))
    # overview -> text, year -> int
    monkeypatch.setattr(
        console,
        "column_types",
        lambda db, table, settings=None: {"overview": "text", "year": "int"},
    )
    monkeypatch.setattr(
        console,
        "read_pk_columns",
        lambda db, table, pk, columns, limit=1000, settings=None: [
            {"pk": 1, "overview": "A heist in dreams", "year": 2010},
            {"pk": 2, "overview": "A space epic", "year": 1968},
        ],
    )
    seen: list[str] = []

    def _capture(text, settings=None):
        seen.append(text)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(vectors, "embed_text", _capture)

    result = vectors.build_index("shop", "films", ["overview", "year"])

    assert result["status"] == "ok"
    assert result["indexed"] == 2
    # numeric field reported, text column split out from it
    assert {"name": "year", "type": "int"} in result["numeric_fields"]
    assert result["text_columns"] == ["overview"]
    # embedding text is built from the TEXT column only (no "year:" line)
    assert seen[0].startswith("overview: A heist in dreams")
    assert "year:" not in seen[0]
    # the schema declared a numeric scalar field "year" as INT64
    assert ("year", "INT64") in record["schema_fields"]
    # insert order: pks, vectors, texts, <year values>
    inserted = record["inserted"]
    assert inserted[0] == [1, 2]  # pks
    assert inserted[3] == [2010, 1968]  # aligned int values


def test_index_float_numeric_column_uses_double(
    monkeypatch, stub_validation, ok_ollama
):
    """A DECIMAL/float column is stored as a DOUBLE scalar field."""
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))
    monkeypatch.setattr(
        console,
        "column_types",
        lambda db, table, settings=None: {"overview": "text", "rating": "decimal"},
    )
    monkeypatch.setattr(
        console,
        "read_pk_columns",
        lambda db, table, pk, columns, limit=1000, settings=None: [
            {"pk": 1, "overview": "great film", "rating": "4.5"},
        ],
    )
    result = vectors.build_index("shop", "films", ["overview", "rating"])
    assert {"name": "rating", "type": "float"} in result["numeric_fields"]
    assert ("rating", "DOUBLE") in record["schema_fields"]
    assert record["inserted"][3] == [4.5]


def test_list_filter_fields_returns_numeric_fields(monkeypatch, client):
    """GET /.../fields returns the collection's numeric scalar fields only."""
    record = {}
    fake = _make_fake_pymilvus(
        record, extra_fields=[("year", "INT64"), ("rating", "DOUBLE")]
    )
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.get("/milvus/collections/shop_films/fields")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "shop_films"
    assert {"name": "year", "type": "int"} in body["fields"]
    assert {"name": "rating", "type": "float"} in body["fields"]
    # reserved fields are excluded
    names = [f["name"] for f in body["fields"]]
    assert "pk" not in names and "embedding" not in names and "text" not in names


def test_list_filter_fields_unreachable(client):
    """No pymilvus available -> graceful unreachable payload, HTTP 200."""
    sys.modules.pop("pymilvus", None)
    resp = client.get("/api/milvus/collections/shop_films/fields")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"] == []
    assert body["status"] == "unreachable"


def test_search_with_numeric_filter_builds_expr(monkeypatch, ok_ollama, client):
    """A numeric filter is compiled into the Milvus ``expr`` for the search."""
    record = {}
    fake = _make_fake_pymilvus(record, extra_fields=[("year", "INT64")])
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.post(
        "/milvus/collections/shop_films/search",
        json={
            "query": "space",
            "top_k": 5,
            "filters": [{"field": "year", "op": "gte", "value": 2000}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # int-kind field -> integer literal, not 2000.0
    assert record["search"]["expr"] == "year >= 2000"


def test_search_multiple_filters_joined_with_and(monkeypatch, ok_ollama, client):
    record = {}
    fake = _make_fake_pymilvus(
        record, extra_fields=[("year", "INT64"), ("rating", "DOUBLE")]
    )
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.post(
        "/milvus/collections/shop_films/search",
        json={
            "query": "space",
            "filters": [
                {"field": "year", "op": "gte", "value": 2000},
                {"field": "rating", "op": "gt", "value": 4},
            ],
        },
    )
    assert resp.status_code == 200
    assert record["search"]["expr"] == "year >= 2000 and rating > 4.0"


def test_search_no_filters_expr_is_none(monkeypatch, ok_ollama, client):
    record = {}
    monkeypatch.setitem(sys.modules, "pymilvus", _make_fake_pymilvus(record))
    resp = client.post(
        "/milvus/collections/shop_films/search",
        json={"query": "space", "top_k": 3},
    )
    assert resp.status_code == 200
    assert record["search"]["expr"] is None


def test_search_unknown_filter_field_returns_error(monkeypatch, ok_ollama, client):
    """Filtering on a field that is not a numeric scalar field -> status:error."""
    record = {}
    # No numeric fields on the collection.
    fake = _make_fake_pymilvus(record)
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.post(
        "/milvus/collections/shop_films/search",
        json={
            "query": "space",
            "filters": [{"field": "year", "op": "gte", "value": 2000}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "unknown filter field" in body["message"]
    assert body["results"] == []
    # the search itself was never executed
    assert "search" not in record


def test_search_unknown_filter_op_returns_error(monkeypatch, ok_ollama, client):
    record = {}
    fake = _make_fake_pymilvus(record, extra_fields=[("year", "INT64")])
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    resp = client.post(
        "/milvus/collections/shop_films/search",
        json={
            "query": "space",
            "filters": [{"field": "year", "op": "between", "value": 2000}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "unknown filter op" in body["message"]


# --------------------------------------------------------------------------
# Source-row hydration (search results enriched with the full MariaDB row)
# --------------------------------------------------------------------------
_SOURCE_META = '{"database": "movies_db", "table": "films", "pk_column": "id"}'


def test_search_hydrates_results_with_source_row(monkeypatch, ok_ollama, client):
    """A search hit is enriched with its full source MariaDB row under
    ``source`` so the UI can show columns (e.g. ``actors``) that were never
    embedded. The source coordinates come from the schema description written
    at index time; the row is resolved by primary key via
    ``console.read_rows_by_pks``.
    """
    record = {}
    fake = _make_fake_pymilvus(record, schema_description=_SOURCE_META)
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    seen = {}

    def _fake_read_rows_by_pks(db, table, pk_column, pks, settings=None):
        seen["args"] = (db, table, pk_column, list(pks))
        return {
            1: {
                "id": 1,
                "title": "Shawshank",
                "actors": "Tim Robbins, Morgan Freeman",
                "year": 1994,
            }
        }

    monkeypatch.setattr(console, "read_rows_by_pks", _fake_read_rows_by_pks)

    resp = client.post(
        "/milvus/collections/movies_db_films/search",
        json={"query": "prison drama", "top_k": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"

    # hydration used the coordinates stored in the schema description
    assert seen["args"][0] == "movies_db"
    assert seen["args"][1] == "films"
    assert seen["args"][2] == "id"
    assert set(seen["args"][3]) == {3, 1}

    by_pk = {r["pk"]: r for r in body["results"]}
    # pk 1 resolved -> full source row present, including the un-embedded actors
    assert by_pk[1]["source"]["actors"] == "Tim Robbins, Morgan Freeman"
    assert by_pk[1]["source"]["title"] == "Shawshank"
    assert by_pk[1]["source"]["year"] == 1994
    # base search fields are still intact
    assert by_pk[1]["text"] == "account settings overview"
    assert by_pk[1]["score"] == 0.72
    # pk 3 had no matching source row -> left without a ``source`` key
    assert "source" not in by_pk[3]


def test_search_hydration_is_best_effort_on_error(monkeypatch, ok_ollama, client):
    """If resolving source rows raises (e.g. MariaDB unreachable), the search
    still succeeds and returns results WITHOUT a ``source`` key — hydration is
    strictly best-effort and never breaks the search."""
    record = {}
    fake = _make_fake_pymilvus(record, schema_description=_SOURCE_META)
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    def _boom(db, table, pk_column, pks, settings=None):
        raise RuntimeError("mariadb unreachable")

    monkeypatch.setattr(console, "read_rows_by_pks", _boom)

    resp = client.post(
        "/milvus/collections/movies_db_films/search",
        json={"query": "prison drama", "top_k": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [r["pk"] for r in body["results"]] == [3, 1]
    # results returned, but none carry a source (hydration failed silently)
    assert all("source" not in r for r in body["results"])


def test_search_without_metadata_skips_hydration(monkeypatch, ok_ollama, client):
    """An older collection whose schema description is not JSON metadata simply
    skips hydration: results have only {pk, text, score} and no ``source``."""
    record = {}
    # default schema_description is "" -> not JSON -> hydration skipped
    fake = _make_fake_pymilvus(record)
    monkeypatch.setitem(sys.modules, "pymilvus", fake)

    def _should_not_be_called(*args, **kwargs):  # pragma: no cover
        raise AssertionError("read_rows_by_pks must not run without metadata")

    monkeypatch.setattr(console, "read_rows_by_pks", _should_not_be_called)

    resp = client.post(
        "/milvus/collections/shop_faqs/search",
        json={"query": "hello", "top_k": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert all(set(r) == {"pk", "text", "score"} for r in body["results"])
