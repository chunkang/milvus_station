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


def _make_fake_pymilvus(record, connect_error=False):
    mod = types.ModuleType("pymilvus")

    class DataType:
        INT64 = "INT64"
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
        def __init__(self, fields):
            self.fields = fields

    _DEFAULT_FIELDS = [
        FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=3),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=100),
    ]

    class Collection:
        def __init__(self, name, schema=None):
            self.name = name
            self.schema = schema if schema is not None else _Schema(_DEFAULT_FIELDS)

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
            self, data, anns_field, param, limit, output_fields=None
        ):
            record["search"] = {
                "data": data,
                "anns_field": anns_field,
                "param": param,
                "limit": limit,
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
