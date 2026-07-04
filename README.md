# milvus_station

Dockerized "station" for a Milvus-backed vector application. A single
`docker-compose.yml` brings up an 8-container topology in a healthy state and
delivers the **hello-world milestone** (SPEC-INFRA-001): the ingress path
(browser -> nginx -> React build) and the admin path
(browser -> nginx -> phpMyAdmin -> MariaDB) work end to end.

> Scope note: This milestone is **infrastructure + hello-world only**. All
> services are scaffolded and healthy, but the embedding (`/api/embed`) and
> vector-search (`/api/search`) round-trip logic is **DEFERRED to
> SPEC-SEARCH-002**. The Milvus and Ollama services run and are reachable;
> they are not yet wired into user-facing search behavior.

## Prerequisites

- Docker Engine
- Docker Compose v2 (the `docker compose` plugin)
- Host TCP port `38005` free (the sole published ingress port)

## Quick start

```bash
cp .env.example .env          # safe local defaults; edit as needed
docker compose up -d --build  # build images and start all 8 services
docker compose ps             # watch services become healthy
```

Then open:

| URL                                   | What you get                                            |
|---------------------------------------|---------------------------------------------------------|
| http://localhost:38005                | React "hello world" page with a link to `/mysql`        |
| http://localhost:38005/mysql          | phpMyAdmin login (use `milvus` / `milvus`)              |
| http://localhost:38005/api/health     | FastAPI aggregated health JSON (mariadb/milvus/ollama)  |

## Services

Eight containers run on a single isolated bridge network and communicate by
service name. Only **nginx** publishes a host port.

| Service     | Image                                    | Role                                        | Host port |
|-------------|------------------------------------------|---------------------------------------------|-----------|
| nginx       | built from `nginx/Dockerfile`            | Sole ingress; serves React build + proxy    | `38005`   |
| fastapi     | built from `services/backend`            | Backend API, `/health` aggregation          | internal  |
| mariadb     | `mariadb:11.4`                           | Relational store                            | internal  |
| phpmyadmin  | `phpmyadmin:5.2`                         | DB admin UI (via `/mysql`)                  | internal  |
| milvus      | `milvusdb/milvus:v2.5.4`                 | Vector store (standalone)                   | internal  |
| etcd        | `quay.io/coreos/etcd:v3.5.16`            | Milvus metadata                             | internal  |
| minio       | `minio/minio:RELEASE.2023-03-20T20-16-18Z` | Milvus object storage                     | internal  |
| ollama      | `ollama/ollama:0.5.4`                    | Embedding runtime (CPU)                     | internal  |

> The React frontend is a static build artifact copied into the nginx image;
> it is not a separate long-running service.

Named volumes persist state across restarts: `mariadb_data`, `etcd_data`,
`minio_data`, `milvus_data`, `ollama_data`.

## Startup ordering

- `etcd` + `minio` healthy -> `milvus` starts
- `mariadb` healthy -> `phpmyadmin` starts
- `mariadb` + `milvus` + `ollama` healthy -> `fastapi` starts
- `nginx` starts alongside the backend and never blocks `/` on backend health,
  so the hello-world page renders even while the backend is warming (N4).

## Configuration

All configuration comes from environment variables documented in
`.env.example`. The real `.env` is git-ignored; no secrets are committed to
source (N1). See `.env.example` for every variable and its default.

## Validate without starting

`docker compose config` renders and validates the merged configuration without
requiring the Docker daemon or pulling images:

```bash
docker compose config            # full rendered config
docker compose config --services # list the 8 service names
```

## Deferred work

Embedding generation, vector search, collection schema, and the search UI are
tracked under **SPEC-SEARCH-002** and are intentionally not implemented here.
