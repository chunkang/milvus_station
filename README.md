# milvus_station

A self-contained **semantic vector-search platform**, delivered as a single
Docker stack. Store text in **MariaDB**, turn it into embeddings with a **Llama**
model (served by **Ollama**), index those vectors in **Milvus**, and run
meaning-based similarity search over them — all from a modern **React + shadcn/ui**
admin console behind a single **nginx** ingress.

The whole pipeline runs from one `docker-compose.yml`; the only host port
published is **`38005`**.

## Architecture

```
                         ┌──────────────────────────────────────────┐
  Browser ──▶ nginx ──▶  │  /       React admin console (shadcn/ui)  │
            (:38005)     │  /mysql  phpMyAdmin                       │
                         │  /api    FastAPI backend                  │
                         └──────────────────────────────────────────┘

  Data pipeline:
  MariaDB (source text) ─▶ FastAPI ─▶ Ollama · Llama (nomic-embed-text, 768-dim)
                                        └─▶ Milvus (IVF_FLAT / COSINE)  ◀─ etcd + minio
                                              └─▶ semantic search results
```

| Component            | Role                                                            |
|----------------------|-----------------------------------------------------------------|
| **nginx**            | Sole ingress on `:38005`; serves the React build + proxies `/mysql` and `/api` |
| **React + shadcn/ui**| Admin console (Main / Source / Milvus / mysqladmin)             |
| **FastAPI**          | Backend API: browse MySQL, index columns, search collections    |
| **MariaDB**          | Relational store — the source-of-truth text                     |
| **phpMyAdmin**       | Database admin UI (at `/mysql`)                                  |
| **Ollama**           | Llama embedding runtime (`nomic-embed-text`, 768-dim, CPU)       |
| **Milvus**           | Vector store / similarity search (standalone)                   |
| **etcd + minio**     | Milvus metadata + object storage                                |
| **ollama-init**      | One-shot: pulls the embedding model on first startup            |

## Prerequisites

- Docker Engine + Docker Compose v2 (the `docker compose` plugin)
- Host TCP port `38005` free

## Quick start

There are two ways to bring the stack up.

### Option A — `run_debug.sh` (recommended for local development / debug mode)

The repository ships a **debug launcher** that does everything for you:

```bash
./run_debug.sh
```

`run_debug.sh` runs the stack in **debug mode** and:

1. **Force-installs prerequisites** — Homebrew (macOS), Docker, and the Docker
   Compose plugin if any are missing.
2. **Starts the Docker daemon** and waits until it is ready.
3. Prepares `.env` from `.env.example` if absent.
4. **Builds + pulls** all images with **plain, verbose BuildKit progress**, logging
   everything to `run_debug.log`.
5. **Runs the stack in the FOREGROUND** (not detached) so you see every
   container's logs live — this is the "debug mode".
6. Pulls the embedding model (`nomic-embed-text`) once the stack is healthy.
7. **Opens the frontend** (`http://localhost:38005`) automatically when all
   services report healthy.
8. **Stops all containers** (`docker compose down`) when you terminate it —
   press **Ctrl+C** and it tears the stack down cleanly.

Flags:

```bash
./run_debug.sh --no-open   # bring the stack up but don't open the browser
./run_debug.sh --down      # just tear the stack down and exit
./run_debug.sh --help      # usage
```

### Option B — plain `docker compose`

```bash
cp .env.example .env          # safe local defaults; edit as needed
docker compose up -d --build  # build images and start the stack (detached)
docker compose ps             # watch services become healthy
```

> **Embedding model auto-pull:** the `nomic-embed-text` model is pulled
> automatically by the one-shot `ollama-init` service on first startup (this may
> take a minute). The app comes up immediately; indexing/search works once the
> pull completes. The model is cached in the `ollama_data` volume, so later
> startups are a fast no-op. Manual fallback:
> `docker compose exec ollama ollama pull nomic-embed-text`.

Then open:

| URL                                   | What you get                                           |
|---------------------------------------|--------------------------------------------------------|
| http://localhost:38005                | The admin console (Main page: purpose + architecture)  |
| http://localhost:38005/mysql          | phpMyAdmin login (use `milvus` / `milvus`)             |
| http://localhost:38005/api/health     | FastAPI aggregated health JSON (mariadb/milvus/ollama) |

## Using the console

The three-menu console drives the whole pipeline:

- **Main** — overview of the tool and its architecture.
- **Source** — browse databases → tables → paginated records. For the
  `milvus_station` database an **Import sample tables** button seeds demo data.
  Each table has an **Index to Milvus** button where you pick **one or more
  columns** (multi-select) — including numeric/temporal fields — which are
  combined into a single labelled text per row (`column: value`) before
  embedding. A **Test** button appears once a table has an indexed collection.
- **Milvus** — browse collections and page through their stored vectors (each
  embedding shown as a truncated preview); a **Test** button runs a semantic
  search returning ranked results with scores.
- **mysqladmin** — opens phpMyAdmin (`/mysql`) in a new tab.

**Typical flow:** Import sample tables → pick a table → *Index to Milvus*
(select one or more columns) → *Test* → type a natural-language query → see
ranked matches by meaning. For example, indexing a movie's `title + overview +
actors` together lets a search for *"a hopeful prison friendship"* surface
*The Shawshank Redemption*.

## Sample data

The `milvus_station` importer seeds four demonstration tables (100+ rows each,
programmatically generated with distinct, semantically varied text):

| Table    | Rows | Embeddable column | Notes                                  |
|----------|------|-------------------|----------------------------------------|
| products | 120  | `description`     | varied catalogue items                 |
| articles | 104  | `body`            | short news/blog posts across topics    |
| movies   | 112  | `overview`        | includes an `actors` field per film    |
| faqs     | 110  | `answer`          | support-style Q&A pairs                 |

## Startup ordering

- `etcd` + `minio` healthy → `milvus` starts
- `mariadb` healthy → `phpmyadmin` starts
- `mariadb` + `milvus` + `ollama` healthy → `fastapi` starts
- `nginx` starts alongside the backend and never blocks `/` on backend health
- `ollama-init` runs once `ollama` is healthy, pulls the model, then exits

Named volumes persist state across restarts: `mariadb_data`, `etcd_data`,
`minio_data`, `milvus_data`, `ollama_data`.

## Configuration

All configuration comes from environment variables documented in `.env.example`.
The real `.env` is git-ignored; no secrets are committed to source.

## Validate without starting

```bash
docker compose config            # full rendered config
docker compose config --services # list the service names
```

## Tests

```bash
# backend
cd services/backend && python -m pytest -q

# frontend
cd services/frontend && npm test -- --run
```
