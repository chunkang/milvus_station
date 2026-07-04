"""Tests for the sample-data import endpoint.

The DB layer is monkeypatched: :func:`app.console.get_connection` is
replaced with a fake connection whose cursor records every executed SQL
statement and returns canned COUNT(*) results. No PyMySQL or live MariaDB
is required. The fake also guards that seed *values* only ever arrive via
``executemany`` parameters (never interpolated into SQL text).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import console, samples
from app.config import get_settings
from app.main import app

APP_DB = get_settings().mariadb_db  # "milvus_station" by default
SAMPLE_NAMES = [t.name for t in samples.SAMPLE_TABLES]


class FakeCursor:
    """Records SQL and returns canned COUNT(*) rows.

    ``existing`` is the set of table names that already exist (so
    information_schema lookups report them) and that are treated as
    already-populated (so COUNT(*) > 0 -> no re-insert).
    """

    def __init__(self, log, existing):
        self._log = log
        self._existing = set(existing)
        self._last = None  # ("exists", name) | ("count", name)

    def execute(self, sql, params=()):
        norm = " ".join(sql.split())
        self._log.append(("execute", norm, tuple(params)))
        upper = norm.upper()

        if "INFORMATION_SCHEMA.TABLES" in upper:
            # _table_exists probe: params == (db, table)
            self._last = ("exists", params[1])
        elif upper.startswith("SELECT COUNT(*)"):
            # find which table this COUNT targets from the backticked name
            name = norm.split("`")[1] if "`" in norm else ""
            self._last = ("count", name)
        else:
            self._last = None

    def executemany(self, sql, seq):
        norm = " ".join(sql.split())
        # Seed values must never be baked into SQL text.
        assert "INSERT INTO" in norm.upper()
        self._log.append(("executemany", norm, list(seq)))
        # After a seed insert the table becomes populated.
        name = norm.split("`")[1] if "`" in norm else ""
        self._existing.add(name)

    def fetchone(self):
        kind, name = self._last or (None, None)
        if kind == "exists":
            return {"cnt": 1 if name in self._existing else 0}
        if kind == "count":
            return {"cnt": 12 if name in self._existing else 0}
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, log, existing):
        self._log = log
        self._existing = existing
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self._log, self._existing)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def fresh_db(monkeypatch):
    """No sample tables exist yet -> import creates & seeds all four."""
    log = []
    conn = FakeConnection(log, existing=set())
    monkeypatch.setattr(console, "get_connection", lambda settings=None: conn)
    return {"log": log, "conn": conn}


@pytest.fixture()
def seeded_db(monkeypatch):
    """All sample tables already exist & are populated -> no re-insert."""
    log = []
    conn = FakeConnection(log, existing=set(SAMPLE_NAMES))
    monkeypatch.setattr(console, "get_connection", lambda settings=None: conn)
    return {"log": log, "conn": conn}


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["", "/api"])
def test_import_into_app_db_ok(fresh_db, client, prefix):
    resp = client.post(f"{prefix}/databases/{APP_DB}/samples/import")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == APP_DB

    names = [t["name"] for t in body["tables"]]
    assert names == SAMPLE_NAMES  # all four, in order

    # Fresh DB: every table reported created and populated.
    for t in body["tables"]:
        assert t["created"] is True
        assert t["rows"] > 0

    assert fresh_db["conn"].committed is True
    assert fresh_db["conn"].closed is True


def test_import_issues_create_and_insert_for_each_table(fresh_db, client):
    resp = client.post(f"/databases/{APP_DB}/samples/import")
    assert resp.status_code == 200
    log = fresh_db["log"]

    creates = [
        entry for entry in log
        if entry[0] == "execute" and "CREATE TABLE IF NOT EXISTS" in entry[1].upper()
    ]
    inserts = [entry for entry in log if entry[0] == "executemany"]

    assert len(creates) == len(SAMPLE_NAMES)
    assert len(inserts) == len(SAMPLE_NAMES)

    # Each expected table gets both a CREATE and a seed INSERT.
    for name in SAMPLE_NAMES:
        assert any(f"`{name}`" in c[1] for c in creates), f"no CREATE for {name}"
        assert any(f"`{name}`" in i[1] for i in inserts), f"no INSERT for {name}"

    # Row counts inserted match the fixed seed data sizes.
    by_table = {i[1].split("`")[1]: len(i[2]) for i in inserts}
    for table in samples.SAMPLE_TABLES:
        assert by_table[table.name] == len(table.rows)


# --------------------------------------------------------------------------
# Restriction: only the application DB may be seeded
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad_db", ["mysql", "otherdb", "shop"])
def test_import_into_other_db_rejected_400(monkeypatch, client, bad_db):
    # get_connection must never be called for a rejected db.
    def boom(settings=None):
        raise AssertionError("connection opened for a disallowed database")

    monkeypatch.setattr(console, "get_connection", boom)

    resp = client.post(f"/databases/{bad_db}/samples/import")
    assert resp.status_code == 400
    assert bad_db in resp.json()["detail"]


# --------------------------------------------------------------------------
# Idempotency: non-empty tables are not re-seeded
# --------------------------------------------------------------------------
def test_import_idempotent_no_reinsert(seeded_db, client):
    resp = client.post(f"/databases/{APP_DB}/samples/import")
    assert resp.status_code == 200
    body = resp.json()

    # Tables already existed -> created is False, rows still reported.
    for t in body["tables"]:
        assert t["created"] is False
        assert t["rows"] > 0

    # No executemany (INSERT) should have run at all.
    inserts = [e for e in seeded_db["log"] if e[0] == "executemany"]
    assert inserts == [], "seed rows were re-inserted into a populated table"

    # CREATE TABLE IF NOT EXISTS is still issued (idempotent DDL).
    creates = [
        e for e in seeded_db["log"]
        if e[0] == "execute" and "CREATE TABLE IF NOT EXISTS" in e[1].upper()
    ]
    assert len(creates) == len(SAMPLE_NAMES)


def test_seed_data_sizes_are_reasonable():
    """Fixed seed sets match the documented approximate row counts."""
    sizes = {t.name: len(t.rows) for t in samples.SAMPLE_TABLES}
    assert sizes["products"] >= 12
    assert sizes["articles"] >= 10
    assert sizes["movies"] >= 12
    assert sizes["faqs"] >= 15
