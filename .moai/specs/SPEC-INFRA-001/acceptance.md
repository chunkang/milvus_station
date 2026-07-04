---
id: SPEC-INFRA-001
type: acceptance
version: "1.0.0"
created: "2026-07-03"
updated: "2026-07-03"
author: "Chun Kang"
priority: "HIGH"
---

# Acceptance Criteria: SPEC-INFRA-001

> Dockerized Milvus Station — Infrastructure Scaffolding & Hello-World Milestone
> Tags: `@SPEC:INFRA-001` `@TEST:acceptance`

All scenarios assume the topology has been started via a single `docker compose up` from the project root. Vector search and embedding round-trips are **out of scope** here (deferred to SPEC-SEARCH-002).

---

## 1. Acceptance Scenarios (Given / When / Then)

### AC1 — Hello-world renders at the ingress with a `/mysql` link
> Verifies: E1, N4, U6

- **Given** the stack is up and nginx is listening on host port `38005`,
- **When** a user opens `http://localhost:38005/` in a browser,
- **Then** the page renders "hello world",
- **And** the page contains a visible link pointing to `/mysql`,
- **And** the page renders successfully even if FastAPI, Milvus, or Ollama are still warming (the render does not block on backend availability).

### AC2 — phpMyAdmin login lists the application database
> Verifies: E2, U2

- **Given** MariaDB has completed initialization and phpMyAdmin is reachable via the ingress,
- **When** the user clicks the `/mysql` link and logs in with username `milvus` and password `milvus`,
- **Then** phpMyAdmin authenticates successfully,
- **And** the application schema is listed and browsable,
- **And** the `milvus` user shows full privileges on the application schema.

### AC3 — All 8 services report healthy after bring-up
> Verifies: U1, U6, U7, U3, U4

- **Given** a clean environment with no prior containers,
- **When** the operator runs `docker compose up` and waits for startup to settle,
- **Then** all 8 containers — `nginx`, `fastapi`, `mariadb`, `phpmyadmin`, `milvus`, `etcd`, `minio`, `ollama` — report a healthy/running state,
- **And** `milvus` only became healthy after `etcd` and `minio` were healthy,
- **And** `fastapi` only became healthy after `mariadb`, `milvus`, and `ollama` were healthy.

### AC4 — `/health` aggregates MariaDB + Milvus + Ollama reachability
> Verifies: U5, S1, S3, N3

- **Given** the backend is running and routed through nginx `/api`,
- **When** a client requests `GET http://localhost:38005/api/health`,
- **Then** the response includes a per-component status for `mariadb`, `milvus`, and `ollama`,
- **And** each reachable component reports `ready`,
- **And** Milvus reports `degraded` when etcd/minio are unhealthy,
- **And** Ollama reports `warming` while its model is still downloading.

---

## 2. Edge Cases

### EC1 — Model still downloading → hello-world still renders (decoupling)
> Verifies: N4, S3

- **Given** the Ollama container has started but its model download is still in progress,
- **When** a user opens `http://localhost:38005/`,
- **Then** the "hello world" page still renders normally,
- **And** `GET /api/health` reports the `ollama` component as `warming` (not a hard failure).

### EC2 — etcd/minio unhealthy → `/health` degraded, frontend unaffected
> Verifies: S1, N4

- **Given** etcd or MinIO is unhealthy,
- **When** the client requests `/api/health` and separately loads `/`,
- **Then** the `milvus` component reports `degraded`,
- **And** the hello-world page at `/` still renders unaffected.

### EC3 — Both `/mysql` and `/mysql/` resolve
> Verifies: U6

- **Given** the nginx ingress is configured for the `/mysql` sub-path,
- **When** the user navigates to `/mysql` (no trailing slash) and to `/mysql/` (with trailing slash),
- **Then** both URLs load the phpMyAdmin interface correctly,
- **And** phpMyAdmin assets and redirects resolve properly (via `PMA_ABSOLUTE_URI`).

### EC4 — Full restart persists MariaDB user + Milvus + Ollama model via volumes
> Verifies: U4

- **Given** the stack has run once (MariaDB user seeded, Milvus initialized, Ollama model pulled),
- **When** the operator runs `docker compose down` (without `-v`) then `docker compose up` again,
- **Then** the `milvus` MariaDB user still exists and can log in,
- **And** Milvus data persists via its named volumes,
- **And** the previously pulled Ollama model is still present (no re-download required).

### EC5 — Wrong DB credentials are denied
> Verifies: U2, N1

- **Given** phpMyAdmin is reachable,
- **When** a user attempts to log in with incorrect credentials (not `milvus`/`milvus`),
- **Then** authentication is rejected,
- **And** no access to the application schema is granted.

---

## 3. Success Criteria

- AC1–AC4 all pass.
- EC1–EC5 all behave as specified.
- The entire topology is defined in a single `docker-compose.yml`.
- Only nginx (`38005`) is published to the host; internal service ports are not exposed beyond development needs.
- No hard-coded secrets exist in committed source; all secrets flow from `.env` (git-ignored) templated by `.env.example`.

---

## 4. Quality Gate Criteria

| Gate | Criterion | Pass Condition |
|------|-----------|----------------|
| Secrets (N1) | No credential literals in committed source | Secret scan clean; only `${VAR}` references + `.env.example` |
| Port exposure (N2) | Only nginx exposed to host | Compose `ports:` review shows only `38005` published |
| Startup ordering (U7) | Dependencies healthy before dependents | `depends_on: service_healthy` present for milvus, phpmyadmin, fastapi |
| Persistence (U4) | Named volumes for stateful services | Volumes defined for mariadb, minio, etcd, milvus, ollama |
| Decoupling (N4) | `/` independent of backend | `GET /` returns 200 with backend down/warming |
| Health aggregation (U5) | `/health` reports 3 components | Response contains mariadb, milvus, ollama statuses |
| Scope boundary | No embed/search logic | `/api/embed` and `/api/search` NOT implemented (deferred) |

---

## 5. Definition of Done

- [ ] Single `docker-compose.yml` brings up all 8 services healthy (AC3).
- [ ] `http://localhost:38005/` renders "hello world" + `/mysql` link (AC1).
- [ ] phpMyAdmin login with `milvus`/`milvus` lists the app DB (AC2).
- [ ] `/api/health` aggregates MariaDB + Milvus + Ollama (AC4).
- [ ] `/mysql` and `/mysql/` both resolve (EC3).
- [ ] State persists across full restart via named volumes (EC4).
- [ ] Wrong credentials denied (EC5).
- [ ] No hard-coded secrets; only nginx exposed to host (quality gates N1, N2).
- [ ] Embedding/search round-trip logic confirmed deferred to SPEC-SEARCH-002.
