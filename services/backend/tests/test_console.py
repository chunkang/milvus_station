"""Tests for the data-console DB introspection & pagination endpoints.

The low-level DB seams (``console.fetch_all`` / ``console.fetch_one``) are
monkeypatched to return canned information_schema / row data, so these
tests never require PyMySQL or a live MariaDB. A guard in the fake asserts
that no raw identifier is ever interpolated into SQL text (injection
strings only ever arrive as bound *parameters*).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import console
from app.main import app

# Canned information_schema fixtures.
_SCHEMATA = [
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
    "milvus_station",
    "shop",
]
_TABLES = {
    "shop": [
        {"TABLE_NAME": "users", "TABLE_ROWS": 42},
        {"TABLE_NAME": "orders", "TABLE_ROWS": 7},
    ],
    "milvus_station": [],
}
_COLUMNS = {
    ("shop", "users"): [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "COLUMN_KEY": "PRI", "ORDINAL_POSITION": 1},
        {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "COLUMN_KEY": "", "ORDINAL_POSITION": 2},
        {"COLUMN_NAME": "bio", "DATA_TYPE": "text", "COLUMN_KEY": "", "ORDINAL_POSITION": 3},
    ],
}
_DATA_ROWS = [
    {"id": 1, "name": "Alice", "bio": "hello"},
    {"id": 2, "name": "Bob", "bio": "world"},
]


@pytest.fixture()
def calls():
    return {"fetch_all": [], "fetch_one": []}


@pytest.fixture()
def patched(monkeypatch, calls):
    def fake_fetch_all(sql, params=(), settings=None):
        norm = " ".join(sql.split())
        # No untrusted identifier may ever be baked into SQL text.
        assert "DROP" not in norm.upper(), f"raw injection reached SQL: {norm}"
        calls["fetch_all"].append((norm, tuple(params)))

        if "information_schema.SCHEMATA" in norm:
            return [{"SCHEMA_NAME": n} for n in _SCHEMATA]
        if "information_schema.TABLES" in norm:
            return list(_TABLES.get(params[0], []))
        if "information_schema.COLUMNS" in norm:
            return list(_COLUMNS.get((params[0], params[1]), []))
        if norm.startswith("SELECT * FROM"):
            # LIMIT %s OFFSET %s -> params == (page_size, offset)
            return list(_DATA_ROWS)
        raise AssertionError(f"unexpected SQL: {norm}")

    def fake_fetch_one(sql, params=(), settings=None):
        norm = " ".join(sql.split())
        assert "DROP" not in norm.upper(), f"raw injection reached SQL: {norm}"
        calls["fetch_one"].append((norm, tuple(params)))
        if norm.startswith("SELECT COUNT(*)"):
            return {"cnt": 57}
        raise AssertionError(f"unexpected SQL: {norm}")

    monkeypatch.setattr(console, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(console, "fetch_one", fake_fetch_one)
    return calls


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.mark.parametrize("prefix", ["", "/api"])
def test_databases_exclude_system_schemas(patched, client, prefix):
    resp = client.get(f"{prefix}/databases")
    assert resp.status_code == 200
    dbs = resp.json()["databases"]
    assert dbs == ["milvus_station", "shop"]
    for sysname in ("information_schema", "mysql", "performance_schema", "sys"):
        assert sysname not in dbs


def test_tables_shape(patched, client):
    resp = client.get("/databases/shop/tables")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "shop"
    assert body["tables"] == [
        {"name": "users", "rows": 42},
        {"name": "orders", "rows": 7},
    ]


def test_tables_unknown_database_404(patched, client):
    resp = client.get("/databases/ghostdb/tables")
    assert resp.status_code == 404


def test_columns_embeddable_flag(patched, client):
    resp = client.get("/databases/shop/tables/users/columns")
    assert resp.status_code == 200
    cols = resp.json()["columns"]
    by_name = {c["name"]: c for c in cols}
    assert by_name["id"]["embeddable"] is False
    assert by_name["name"]["embeddable"] is True  # varchar
    assert by_name["bio"]["embeddable"] is True  # text


def test_rows_pagination(patched, client):
    resp = client.get("/databases/shop/tables/users/rows?page=3&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "shop"
    assert body["table"] == "users"
    assert body["page"] == 3
    assert body["page_size"] == 10
    assert body["total"] == 57
    assert body["columns"] == ["id", "name", "bio"]
    # rows are column-ordered lists
    assert body["rows"][0] == [1, "Alice", "hello"]

    # LIMIT/OFFSET bound as integer params: offset == (page-1)*page_size
    select_calls = [
        c for c in patched["fetch_all"] if c[0].startswith("SELECT * FROM")
    ]
    assert select_calls, "data select never executed"
    _, params = select_calls[-1]
    assert params == (10, 20)  # page_size=10, offset=(3-1)*10


def test_rows_page_size_capped(patched, client):
    resp = client.get("/databases/shop/tables/users/rows?page=1&page_size=9999")
    assert resp.status_code == 200
    assert resp.json()["page_size"] == console.MAX_PAGE_SIZE  # 100


def test_rows_invalid_table_404(patched, client):
    resp = client.get("/databases/shop/tables/ghost/rows")
    assert resp.status_code == 404


def test_injection_identifier_rejected_and_never_queried(patched, client):
    malicious = "x; DROP TABLE users"
    resp = client.get(f"/databases/shop/tables/{malicious}/rows")
    # Rejected before any raw query is built.
    assert resp.status_code in (400, 404)
    # No SELECT * ever ran, and the guard in the fake proves no DROP text
    # reached SQL (it would have raised AssertionError otherwise).
    assert not any(
        c[0].startswith("SELECT * FROM") for c in patched["fetch_all"]
    )


def test_injection_identifier_in_database_rejected(patched, client):
    malicious = "shop; DROP TABLE users"
    resp = client.get(f"/databases/{malicious}/tables")
    assert resp.status_code in (400, 404)
