"""Environment-driven configuration for the backend service.

All settings are read from environment variables at instantiation time.
Defaults match the docker-compose service names so the service works
out-of-the-box inside the compose network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    """Read an environment variable, falling back to a default."""
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to a default."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable service settings sourced from the environment.

    Defaults intentionally match docker-compose service hostnames
    (mariadb, milvus, ollama). etcd/minio are Milvus internal
    dependencies and are not probed directly by this service; they
    surface indirectly through the Milvus "degraded" state.
    """

    # MariaDB (relational metadata store)
    mariadb_host: str = field(default_factory=lambda: _env("MARIADB_HOST", "mariadb"))
    mariadb_port: int = field(default_factory=lambda: _env_int("MARIADB_PORT", 3306))
    mariadb_user: str = field(default_factory=lambda: _env("MARIADB_USER", "milvus"))
    mariadb_password: str = field(
        default_factory=lambda: _env("MARIADB_PASSWORD", "milvus")
    )
    mariadb_db: str = field(default_factory=lambda: _env("MARIADB_DATABASE", "milvus_station"))

    # Milvus (vector store)
    milvus_host: str = field(default_factory=lambda: _env("MILVUS_HOST", "milvus"))
    milvus_port: int = field(default_factory=lambda: _env_int("MILVUS_PORT", 19530))

    # Ollama (embedding model host)
    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://ollama:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "nomic-embed-text")
    )

    # Milvus internal deps (not directly probed, documented for completeness)
    etcd_endpoint: str = field(default_factory=lambda: _env("ETCD_ENDPOINT", "etcd:2379"))
    minio_endpoint: str = field(default_factory=lambda: _env("MINIO_ENDPOINT", "minio:9000"))

    # Probe tuning
    probe_timeout_seconds: float = field(
        default_factory=lambda: float(_env("PROBE_TIMEOUT_SECONDS", "3.0"))
    )


def get_settings() -> Settings:
    """Construct a fresh Settings instance from the current environment.

    Returns a new object each call so tests can mutate os.environ and
    observe the effect without module-level caching.
    """
    return Settings()
