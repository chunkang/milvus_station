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
            record["query"] = {"expr": expr, "offset": offset, "limit": limit}
            return [{"pk": 1, "text": "hello"}]

    class connections:
        @staticmethod
        def connect(**kw):
            if connect_error:
                raise ConnectionError("milvus unreachable")
            record["connected"] = kw

    class utility:
        @staticmethod
        def has_collection(name):
            return False

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
    # embedding (FLOAT_VECTOR) excluded from output fields
    assert "embedding" not in body["fields"]
    assert body["rows"] == [{"pk": 1, "text": "hello"}]
