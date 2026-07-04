---
id: SPEC-INFRA-001
type: plan
version: "1.0.0"
created: "2026-07-03"
updated: "2026-07-03"
author: "Chun Kang"
priority: "HIGH"
---

# Implementation Plan: SPEC-INFRA-001

> Dockerized Milvus Station — Infrastructure Scaffolding & Hello-World Milestone
> Tags: `@SPEC:INFRA-001` `@DOMAIN:infrastructure`

## 1. Objective

Deliver a single `docker-compose.yml` that stands up all 8 services in a healthy state and proves two end-to-end paths:
1. Browser → nginx (`38005`) → React static "hello world" (+ link to `/mysql`).
2. Browser → nginx → phpMyAdmin → MariaDB (`milvus`/`milvus`).

The Milvus stack and Ollama must be scaffolded and healthy, but embedding/search request logic is **deferred to SPEC-SEARCH-002**.

---

## 2. Technology Stack (candidate versions — verify exact pins at run stage)

| Component  | Candidate Image / Version                     | Notes |
|------------|-----------------------------------------------|-------|
| MariaDB    | `mariadb:11.4`                                | App DB; init SQL seeds `milvus` user + schema. |
| phpMyAdmin | `phpmyadmin:5.2`                              | Requires `PMA_ABSOLUTE_URI` for `/mysql` sub-path. |
| Milvus     | `milvusdb/milvus:v2.5.x` (standalone)        | Pin exact patch at run stage. |
| etcd       | `quay.io/coreos/etcd:v3.5.x`                  | Milvus metadata store. |
| MinIO      | `minio/minio` (recent stable)                | Milvus object storage. |
| Ollama     | `ollama/ollama` (recent stable)              | CPU default; model pulled at runtime into named volume. |
| Backend    | `python:3.13-slim`; FastAPI `>=0.115`; `pymilvus` matching Milvus 2.5 | `/health` only at this stage. |
| Frontend   | `node:22-alpine` (build) → `nginx:1.27-alpine` (serve); React 19 + Vite | Static build served by nginx. |

> Exact version pins (including `pymilvus`/Milvus compatibility and the Ollama model tag) are confirmed by the implementation agent at `/moai:2-run`.

---

## 3. Directory Layout

```
milvus_station/
├── docker-compose.yml            # single source of orchestration (root)
├── .env.example                  # committed secret template
├── .env                          # local secrets (git-ignored)
├── nginx/
│   └── default.conf              # ingress routing: / , /mysql , /api
├── services/
│   ├── backend/                  # FastAPI
│   │   ├── Dockerfile
│   │   ├── app/                  # /health aggregation
│   │   └── requirements.txt
│   └── frontend/                 # React (Vite, React 19)
│       ├── Dockerfile            # node build -> nginx serve (or multi-stage)
│       ├── index.html
│       └── src/                  # hello-world + /mysql link
└── mariadb/
    └── init/
        └── 01-init.sql           # create milvus user + app schema (+ optional demo seed)
```

---

## 4. Service Dependency Graph

```
etcd  ─┐
minio ─┴─► milvus ─┐
                   ├─► fastapi ─► nginx (ingress :38005)
mariadb ──────────┤
   └─► phpmyadmin  │
ollama ───────────┘
```

- `etcd`, `minio` healthy → `milvus`.
- `mariadb` healthy → `phpmyadmin`.
- `ollama` healthy (independent).
- `mariadb` + `milvus` + `ollama` healthy → `fastapi`.
- `fastapi` healthy → nginx `/api` fully operational.

---

## 5. Implementation Sequence (task decomposition)

Ordered by dependency. No time estimates; sequencing expresses "complete A, then start B".

1. **Scaffold layout** — Create directory tree, placeholder Dockerfiles, `.env.example`.
2. **Compose skeleton** — Define isolated bridge network, named volumes, and 8 service stubs (no logic yet).
3. **MariaDB + init SQL** — Add `mariadb` service, named volume, healthcheck, and `01-init.sql` creating `milvus`/`milvus` with full privileges on the app schema.
4. **phpMyAdmin** — Add `phpmyadmin` service with `PMA_ABSOLUTE_URI` set for the `/mysql` sub-path; `depends_on` mariadb healthy.
5. **nginx ingress** — Add `nginx` on `38005` with routing for `/`, `/mysql/` (trailing-slash handling), `/api/`.
6. **React hello-world** — Build React 19 (Vite) static assets rendering "hello world" + link to `/mysql`; serve via nginx. Must render independent of backend (N4).
7. **FastAPI /health** — Add backend service exposing `/health` aggregating MariaDB + Milvus + Ollama reachability; route via nginx `/api`.
8. **Milvus stack** — Add `etcd`, `minio`, then `milvus` (standalone) with healthchecks and ordered `depends_on`; named volumes for etcd/minio/milvus.
9. **Ollama service** — Add `ollama` with a named volume for models; pull model at runtime; report `warming` while downloading.
10. **Bring-up validation** — `docker compose up`; verify all 8 healthy, `/` renders, `/mysql` logs in, `/health` aggregates, persistence across restart.

---

## 6. Milestones (priority-ordered, no time estimates)

- **Primary Goal (Priority High):** Single `docker-compose.yml` brings up MariaDB, phpMyAdmin, nginx, and React hello-world; `/` renders at `:38005` with working `/mysql` login (AC1, AC2).
- **Secondary Goal (Priority High):** FastAPI `/health` live and routed via `/api`; Milvus stack (etcd + minio + milvus) healthy (AC3 partial, AC4).
- **Final Goal (Priority Medium):** Ollama healthy with model pulled into named volume; all 8 services healthy; persistence verified across full restart (AC3 complete, edge cases).
- **Optional Goal (Priority Low):** Demo seed on first boot; optional Attu UI; GPU passthrough scaffolding (deferred).

---

## 7. Technical Approach

- **Single-file orchestration:** everything in one root `docker-compose.yml`; named volumes and one bridge network.
- **Decoupled hello-world:** the React static build is served directly by nginx so `GET /` never depends on FastAPI/Milvus/Ollama readiness (satisfies N4).
- **Sub-path admin UI:** phpMyAdmin behind `/mysql` requires `PMA_ABSOLUTE_URI` and nginx rewrite/trailing-slash handling so both `/mysql` and `/mysql/` resolve.
- **Health aggregation:** FastAPI `/health` probes MariaDB (connect), Milvus (client ping), Ollama (API reachability), returning per-component `ready`/`degraded`/`warming`.
- **Ordered startup:** healthchecks + `depends_on: condition: service_healthy` enforce the dependency graph.
- **Secrets discipline:** all credentials via `${VAR}` from `.env` (git-ignored); `.env.example` documents each key.

---

## 8. Risk Analysis

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Milvus ↔ `pymilvus` version mismatch. | Medium | High | Pin `pymilvus` to the Milvus 2.5.x compatibility matrix at run stage. |
| R2 | phpMyAdmin sub-path (`/mysql`) breaks assets/redirects. | Medium | Medium | Set `PMA_ABSOLUTE_URI`; handle trailing slash in nginx; test both `/mysql` and `/mysql/`. |
| R3 | Ollama model download slow/fails at first boot. | Medium | Low | Report `warming` in `/health`; decouple hello-world (N4); model wiring deferred to SPEC-SEARCH-002. |
| R4 | Milvus starts before etcd/minio healthy. | Medium | High | Strict `depends_on: service_healthy` + healthchecks (S1). |
| R5 | Port `38005` conflict on host. | Low | Medium | Document required free port; fail fast with clear error. |
| R6 | Accidental secret leakage in committed source. | Low | High | `.env` git-ignored; secret scan in quality gate (N1). |
| R7 | Internal ports exposed to host. | Low | Medium | Only nginx publishes `38005`; review compose `ports:` (N2). |

---

## 9. Scope Boundary — SPEC-SEARCH-002

The following are **explicitly deferred** and MUST NOT be implemented in this SPEC:
- `/api/embed` — text → embedding vector generation via Ollama.
- `/api/search` — query → Milvus vector similarity search round-trip.
- Milvus collection schema, index configuration, and ingestion/upsert pipelines.
- Any search UI beyond the hello-world page.

At this stage the Ollama and Milvus services must simply be **running and healthy**; their request/response logic arrives in **SPEC-SEARCH-002**.

---

## 10. Definition of Done (plan-level)

- `docker compose up` yields 8 healthy containers.
- `GET http://localhost:38005/` renders "hello world" + `/mysql` link.
- `/mysql` and `/mysql/` both load phpMyAdmin; `milvus`/`milvus` login lists the app DB.
- `/api/health` aggregates MariaDB + Milvus + Ollama status.
- No hard-coded secrets; only nginx exposed to host.
- State persists across a full `down`/`up` cycle via named volumes.
