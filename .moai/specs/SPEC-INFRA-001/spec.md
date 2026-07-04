---
id: SPEC-INFRA-001
version: "1.0.0"
status: "draft"
created: "2026-07-03"
updated: "2026-07-03"
author: "Chun Kang"
priority: "HIGH"
---

# SPEC-INFRA-001: Dockerized Milvus Station — Infrastructure Scaffolding & Hello-World Milestone

## HISTORY

| Version | Date       | Author     | Change                                                                 |
|---------|------------|------------|------------------------------------------------------------------------|
| 1.0.0   | 2026-07-03 | Chun Kang  | Initial creation. Infrastructure scaffolding + hello-world milestone. All 8 services scaffolded and healthy via a single docker-compose.yml. Embedding/search round-trip logic explicitly deferred to SPEC-SEARCH-002. |

---

## 1. Overview

This SPEC establishes the containerized foundation ("station") for a Milvus-backed vector application. It delivers a single `docker-compose.yml` that brings up the complete 8-service topology in a healthy state, plus a minimal "hello world" milestone that proves the ingress path (browser → nginx → React static build) and the administrative path (browser → nginx → phpMyAdmin → MariaDB) work end to end.

Scope is deliberately narrow: this is **infrastructure + hello-world only**. All 8 services — including the full Milvus stack (milvus + etcd + minio) and the Ollama embedding runtime — MUST be scaffolded and reach a healthy/running state. However, the **application logic** that performs embedding generation and vector search round-trips (the `/api/embed` and `/api/search` request/response flows) is **explicitly DEFERRED** to a future SPEC (**SPEC-SEARCH-002**). At this stage the services exist and are reachable; they are not yet wired into user-facing search behavior.

### 1.1 Scope Boundary

**In scope (SPEC-INFRA-001):**
- Single `docker-compose.yml` orchestrating all 8 services.
- Named-volume persistence, isolated bridge network, healthchecks, `depends_on` ordering.
- MariaDB with a `milvus`/`milvus` full-privilege application user, seeded via init SQL.
- phpMyAdmin reachable through the nginx ingress at `/mysql`.
- nginx as the sole host ingress on port `38005`, routing `/`, `/mysql`, `/api`.
- React (Vite, React 19) static build rendering "hello world" + a link to `/mysql`.
- FastAPI `/health` endpoint aggregating reachability of MariaDB, Milvus, and Ollama.
- Milvus standalone stack (milvus + etcd + minio) running and healthy.
- Ollama container running and healthy, model pulled at runtime into a named volume (CPU default).
- Secrets provided via `.env.example` + local `.env` (never hard-coded in committed source).

**Out of scope (DEFERRED to SPEC-SEARCH-002):**
- `/api/embed` endpoint logic (text → embedding vector generation via Ollama).
- `/api/search` endpoint logic (query → Milvus vector similarity search round-trip).
- Any user-facing search UI beyond the hello-world page.
- Collection schema design, index tuning, and ingestion pipelines.

---

## 2. Environment

- **Runtime**: Docker Engine + Docker Compose v2, single host.
- **Host ingress**: TCP port `38005` (nginx only). No other service publishes a port to the host beyond development needs.
- **Vector store**: Milvus standalone (`milvus` + `etcd` + `minio`). FAISS-family index is used internally by Milvus; not managed directly.
- **Embeddings runtime**: Ollama (`ollama/ollama`), CPU by default, model pulled at runtime into a named volume.
- **Relational store**: MariaDB, with phpMyAdmin as the web administration UI.
- **Frontend**: React 19 built with Vite into static assets, served by nginx.
- **Backend**: FastAPI (Python 3.13), exposing `/health` internally, routed through nginx `/api`.
- **Network**: single isolated Docker bridge network; services communicate by service name.
- **Persistence**: named Docker volumes for MariaDB data, MinIO data, etcd data, Milvus data, and Ollama models.
- **Secrets**: `.env` file (git-ignored) derived from committed `.env.example`.

---

## 3. Assumptions

| # | Assumption | Confidence | Risk if Wrong |
|---|------------|-----------|---------------|
| A1 | Docker Engine and Compose v2 are installed and the host can pull public images. | High | Bring-up fails; no image pull. |
| A2 | Host port `38005` is free and bindable. | High | Ingress cannot bind; port conflict. |
| A3 | Milvus standalone `v2.5.x` is compatible with a matching `pymilvus` client. | Medium | Backend cannot connect to Milvus. |
| A4 | Ollama can pull the chosen model over the network at first boot into a named volume. | Medium | Ollama stays in "warming" longer; model unavailable (acceptable this SPEC, deferred wiring). |
| A5 | CPU-only inference is acceptable for the milestone (GPU deferred). | High | Slower inference later; irrelevant to hello-world. |
| A6 | The 8-service set is: nginx, react(static via nginx build), fastapi, mariadb, phpmyadmin, milvus, etcd, minio, ollama — with the React build served by nginx (so the counted running services are: nginx, fastapi, mariadb, phpmyadmin, milvus, etcd, minio, ollama = 8). | High | Service count mismatch in validation. |

> Note on service counting: the React frontend is a **static build artifact served by the nginx container**; it is not a long-running service of its own. The 8 running/healthy containers are: **nginx, fastapi, mariadb, phpmyadmin, milvus, etcd, minio, ollama**.

---

## 4. Requirements (EARS)

### 4.1 Ubiquitous Requirements (Always Active)

- **U1** — The system **shall** define and orchestrate the entire topology from a single `docker-compose.yml`.
- **U2** — The system **shall** provision a MariaDB application user `milvus` (password `milvus`) with full privileges on the application schema, seeded via init SQL.
- **U3** — The system **shall** run all services on a single isolated Docker bridge network, with inter-service communication by service name.
- **U4** — The system **shall** persist stateful data using named volumes for MariaDB, MinIO, etcd, Milvus, and Ollama models.
- **U5** — The system **shall** expose a FastAPI `/health` endpoint that reports reachability of MariaDB, Milvus, and Ollama.
- **U6** — The system **shall** expose exactly one host ingress (nginx) on port `38005`, routing `/` to the React static build, `/mysql` to phpMyAdmin, and `/api` to FastAPI.
- **U7** — The system **shall** define healthchecks and `depends_on` ordering so that dependent services start only after their dependencies are healthy.

### 4.2 Event-Driven Requirements (Trigger → Response)

- **E1** — **When** a client issues `GET /` on port `38005`, the system **shall** render a "hello world" page containing a link to `/mysql`.
- **E2** — **When** a user clicks the `/mysql` link, the system **shall** load the phpMyAdmin interface allowing login with the `milvus`/`milvus` credentials.
- **E3** — *(DEFERRED to SPEC-SEARCH-002)* **When** a client posts text to `/api/embed`, the system **shall** return a generated embedding vector via Ollama. *Not implemented in this SPEC; the Ollama service must nonetheless be healthy.*
- **E4** — *(DEFERRED to SPEC-SEARCH-002)* **When** a client posts a query to `/api/search`, the system **shall** perform a Milvus vector similarity search and return ranked results. *Not implemented in this SPEC; the Milvus stack must nonetheless be healthy.*
- **E5** — *(DEFERRED to SPEC-SEARCH-002)* **When** an embedding is generated, the system **shall** upsert it into a Milvus collection. *Not implemented in this SPEC.*

### 4.3 State-Driven Requirements (While Condition Holds)

- **S1** — **While** etcd or MinIO is unhealthy, the Milvus service **shall** refuse connections and the FastAPI `/health` endpoint **shall** report a degraded state for the Milvus component.
- **S2** — **While** MariaDB is initializing, phpMyAdmin **shall** wait (and not report healthy login availability) until MariaDB is ready.
- **S3** — **While** the Ollama model is downloading, the Ollama component in `/health` **shall** report a "warming" state rather than "ready".

### 4.4 Optional Requirements (Where Feasible)

- **O1** — **Where** a compatible GPU is available, the system **shall** support GPU passthrough for Ollama. *(Deferred — CPU default in this SPEC.)*
- **O2** — **Where** first-boot seeding is enabled, the system **shall** load a demo seed dataset into MariaDB.
- **O3** — **Where** desired, the system **shall** support an optional Attu UI container for Milvus inspection.

### 4.5 Unwanted-Behavior Requirements (Prohibitions)

- **N1** — The system **shall not** contain hard-coded secrets in committed source; secrets **shall** be sourced from `.env` (git-ignored), templated by `.env.example`.
- **N2** — The system **shall not** expose internal service ports (MariaDB, etcd, MinIO, Milvus, Ollama) to the host beyond explicit development needs; only nginx `38005` is the public ingress.
- **N3** — The system **shall not** report the frontend/ingress as fully healthy while FastAPI is unreachable through `/api`.
- **N4** — The hello-world render **shall not** block on backend availability; `GET /` **shall** succeed even when FastAPI, Milvus, or Ollama are still warming or unavailable.

---

## 5. Specifications

### 5.1 Service Topology (8 running containers)

| Service     | Image (candidate)             | Role                                   | Host Port |
|-------------|-------------------------------|----------------------------------------|-----------|
| nginx       | `nginx:1.27-alpine`           | Sole ingress; serves React build + proxy | `38005`   |
| fastapi     | `python:3.13-slim` (built)    | Backend API, `/health`                 | internal  |
| mariadb     | `mariadb:11.4`                | Relational store                       | internal  |
| phpmyadmin  | `phpmyadmin:5.2`              | DB admin UI (via `/mysql`)             | internal  |
| milvus      | `milvusdb/milvus:v2.5.x`      | Vector store (standalone)              | internal  |
| etcd        | `quay.io/coreos/etcd:v3.5.x`  | Milvus metadata                        | internal  |
| minio       | `minio/minio` (recent stable) | Milvus object storage                  | internal  |
| ollama      | `ollama/ollama` (recent stable) | Embedding runtime (CPU)              | internal  |

> The React frontend is a static build (`node:22-alpine` build stage) copied into the nginx container; it is not a separate running service.

### 5.2 Ingress Routing (nginx on 38005)

- `/`        → React static build (SPA index).
- `/mysql/`  → phpMyAdmin. Must set `PMA_ABSOLUTE_URI` and correctly handle trailing-slash so both `/mysql` and `/mysql/` resolve.
- `/api/`    → FastAPI upstream.

### 5.3 Dependency & Health Ordering

- `etcd`, `minio` healthy → `milvus` starts.
- `mariadb` healthy → `phpmyadmin` starts.
- `ollama` reaches healthy independently.
- `mariadb` + `milvus` + `ollama` healthy → `fastapi` starts.
- `fastapi` healthy → nginx ingress fully operational for `/api`.

### 5.4 `/health` Aggregation

`GET /api/health` returns per-component status for `mariadb`, `milvus`, `ollama`:
- `ready` when reachable.
- `degraded` for Milvus when etcd/minio unhealthy (S1).
- `warming` for Ollama while the model is downloading (S3).

### 5.5 Secrets

- Committed `.env.example` documents every variable.
- Local `.env` (git-ignored) supplies real values.
- No credential literals in `docker-compose.yml` beyond `${VAR}` references or documented non-sensitive defaults.

---

## 6. Traceability

| Requirement | Verified By (acceptance.md) |
|-------------|-----------------------------|
| U1, U6, U7  | AC3 (all 8 services healthy) |
| U2          | AC2 (phpMyAdmin login lists app DB) |
| U5, S1, S3  | AC4 (`/health` aggregation) |
| E1, N4      | AC1 (hello-world renders), Edge: model downloading |
| E2, U2      | AC2 |
| U3, U4      | AC3, Edge: full restart persistence |
| N1          | Quality gate: secret scan |
| N2          | Quality gate: port exposure review |
| N3          | Edge: FastAPI unreachable |
| E3, E4, E5  | DEFERRED → SPEC-SEARCH-002 |

**Related SPECs:**
- **SPEC-SEARCH-002** *(future)* — Embedding generation (`/api/embed`) and vector search (`/api/search`) round-trip logic, collection schema, and ingestion.

**Tags:** `@SPEC:INFRA-001` `@DOMAIN:infrastructure` `@MILESTONE:hello-world`
