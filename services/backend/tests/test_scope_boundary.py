"""Scope boundary tests.

The embedding and search endpoints are DEFERRED to SPEC-SEARCH-002 and
MUST NOT be implemented in this service. These tests assert they 404,
guarding against accidental scope creep.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/api/embed", "/api/search"])
def test_deferred_endpoints_not_implemented(client, path):
    """Deferred endpoints (SPEC-SEARCH-002) must return 404."""
    get_response = client.get(path)
    post_response = client.post(path, json={})

    assert get_response.status_code == 404
    assert post_response.status_code == 404
