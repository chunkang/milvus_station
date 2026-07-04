"""Tests for the /health aggregation logic.

Component probes are monkeypatched so these tests never require live
MariaDB/Milvus/Ollama services (nor the pymilvus/pymysql packages).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import health as health_module
from app.main import app


def _patch_probes(monkeypatch, *, mariadb, milvus, ollama):
    """Replace the three component probes with fixed async stubs."""

    async def fake_mariadb(settings=None):
        return mariadb

    async def fake_milvus(settings=None):
        return milvus

    async def fake_ollama(settings=None):
        return ollama

    monkeypatch.setattr(health_module, "probe_mariadb", fake_mariadb)
    monkeypatch.setattr(health_module, "probe_milvus", fake_milvus)
    monkeypatch.setattr(health_module, "probe_ollama", fake_ollama)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/health", "/api/health"])
def test_all_ready_overall_ok(monkeypatch, client, path):
    """All components ready -> overall status "ok", HTTP 200."""
    _patch_probes(monkeypatch, mariadb="ready", milvus="ready", ollama="ready")

    response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"] == {
        "mariadb": "ready",
        "milvus": "ready",
        "ollama": "ready",
    }


def test_milvus_degraded_overall_degraded(monkeypatch, client):
    """Milvus degraded (etcd/minio down) -> overall degraded, still 200."""
    _patch_probes(monkeypatch, mariadb="ready", milvus="degraded", ollama="ready")

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["milvus"] == "degraded"


def test_ollama_warming_reported_and_200(monkeypatch, client):
    """Ollama warming (model downloading) -> reported, overall degraded, 200."""
    _patch_probes(monkeypatch, mariadb="ready", milvus="ready", ollama="warming")

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["components"]["ollama"] == "warming"
    assert body["status"] == "degraded"


def test_mariadb_unreachable_reported_and_200(monkeypatch, client):
    """MariaDB unreachable -> reported, overall degraded, still 200."""
    _patch_probes(monkeypatch, mariadb="unreachable", milvus="ready", ollama="ready")

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["components"]["mariadb"] == "unreachable"
    assert body["status"] == "degraded"


@pytest.mark.parametrize("path", ["/health", "/api/health"])
def test_components_have_exact_keys(monkeypatch, client, path):
    """components object must contain exactly mariadb, milvus, ollama."""
    _patch_probes(monkeypatch, mariadb="ready", milvus="degraded", ollama="warming")

    response = client.get(path)

    assert response.status_code == 200
    components = response.json()["components"]
    assert set(components.keys()) == {"mariadb", "milvus", "ollama"}
