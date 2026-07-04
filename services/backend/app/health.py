"""Component health probes.

Each probe is an async function that returns exactly one of the
component status strings:

    "ready"       - component is up and fully usable
    "degraded"    - component is reachable but a dependency is impaired
    "warming"     - component is up but not yet serviceable (e.g. model downloading)
    "unreachable" - component could not be contacted

Probes are intentionally implemented as standalone module-level async
functions so they can be trivially monkeypatched in unit tests. The
aggregation logic (:func:`gather_health`) depends only on these
functions, never on the underlying clients directly.

The Milvus and MariaDB client libraries are imported lazily *inside*
each probe so that unit tests which monkeypatch the probes do not need
those packages installed.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import httpx

from .config import Settings, get_settings

ComponentStatus = Literal["ready", "degraded", "warming", "unreachable"]

# Status constants (avoid magic strings across the codebase).
READY: ComponentStatus = "ready"
DEGRADED: ComponentStatus = "degraded"
WARMING: ComponentStatus = "warming"
UNREACHABLE: ComponentStatus = "unreachable"


async def probe_mariadb(settings: Settings | None = None) -> ComponentStatus:
    """Probe MariaDB with a lightweight connection + ping.

    Returns "ready" on a successful connection/ping, otherwise
    "unreachable". PyMySQL is a synchronous driver, so the blocking
    connect is executed in a worker thread to avoid stalling the loop.
    """
    settings = settings or get_settings()

    def _connect_and_ping() -> bool:
        import pymysql  # lazy import: not required when probe is mocked

        conn = pymysql.connect(
            host=settings.mariadb_host,
            port=settings.mariadb_port,
            user=settings.mariadb_user,
            password=settings.mariadb_password,
            database=settings.mariadb_db,
            connect_timeout=int(settings.probe_timeout_seconds) or 1,
        )
        try:
            conn.ping(reconnect=False)
            return True
        finally:
            conn.close()

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_connect_and_ping),
            timeout=settings.probe_timeout_seconds + 1,
        )
        return READY
    except Exception:
        return UNREACHABLE


async def probe_milvus(settings: Settings | None = None) -> ComponentStatus:
    """Probe Milvus for connectivity and dependency health.

    Returns:
        "ready"    - Milvus responds and reports healthy.
        "degraded" - Milvus is reachable but its backing dependencies
                     (etcd / minio) are down, so it cannot fully serve.
        "unreachable" - Milvus could not be contacted at all.
    """
    settings = settings or get_settings()

    def _check() -> ComponentStatus:
        # Lazy import: pymilvus is heavy and not needed when mocked.
        from pymilvus import MilvusClient

        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        client = MilvusClient(uri=uri, timeout=settings.probe_timeout_seconds)
        try:
            # A basic metadata call. If Milvus is up but etcd/minio are
            # down, the server is reachable but operations that touch
            # storage fail -> treat as degraded.
            client.list_collections()
            return READY
        finally:
            try:
                client.close()
            except Exception:
                pass

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_check),
            timeout=settings.probe_timeout_seconds + 1,
        )
    except ConnectionError:
        # Raised by pymilvus when the server itself cannot be reached.
        return UNREACHABLE
    except Exception:
        # Reachable but an internal dependency (etcd/minio) failed the
        # operation -> degraded rather than fully unreachable.
        return DEGRADED


async def probe_ollama(settings: Settings | None = None) -> ComponentStatus:
    """Probe Ollama by listing available models.

    Returns:
        "ready"       - Ollama responds and has at least one model loaded.
        "warming"     - Ollama responds but has no models yet (model still
                        pulling/downloading on first boot).
        "unreachable" - Ollama could not be contacted.
    """
    settings = settings or get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=settings.probe_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return UNREACHABLE

    models = payload.get("models") or []
    return READY if len(models) > 0 else WARMING


async def gather_health(settings: Settings | None = None) -> dict[str, object]:
    """Run all component probes concurrently and aggregate the result.

    Overall status is "ok" only when every component is "ready";
    otherwise it is "degraded". The service always returns HTTP 200 for
    health so orchestrators can read component detail rather than
    treating any impairment as a hard failure.
    """
    settings = settings or get_settings()

    mariadb_status, milvus_status, ollama_status = await asyncio.gather(
        probe_mariadb(settings),
        probe_milvus(settings),
        probe_ollama(settings),
    )

    components: dict[str, ComponentStatus] = {
        "mariadb": mariadb_status,
        "milvus": milvus_status,
        "ollama": ollama_status,
    }

    overall = "ok" if all(status == READY for status in components.values()) else "degraded"

    return {"status": overall, "components": components}
