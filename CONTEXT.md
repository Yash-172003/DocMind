# DocMind — Project Context & Progress

> This file provides complete context for any AI assistant working on this project.
> Last updated: 2026-08-04

---

## What Is DocMind?

DocMind is a 14-month, 5-phase **Enterprise Document Intelligence Platform** being built as a learning project by Yash (Kanwar Yashwender Singh). The full roadmap lives in `Docs/DocMind.txt`.

**Philosophy:** "The roadmap IS the project. The project IS the roadmap." Every skill feeds directly into the next layer of the same system. Nothing learned in isolation.

**Three Laws:**
1. Build before you fully understand. Confusion after building is the prerequisite for understanding.
2. Measure everything. Every feature gets a metric.
3. Treat confusion as information. Keep a `confusion_log.md`.

**End-State Vision:** A system that ingests any enterprise document (PDF, Word, Excel, email, HTML), extracts structured knowledge with citation grounding, runs autonomous multi-step audit workflows, exposes an MCP server, monitors itself for quality/cost/hallucinations, and deploys on Azure Kubernetes Service.

---

## 5-Phase Overview

| Phase | Title | Timeline | Status |
|-------|-------|----------|--------|
| **Phase 0** | Engineering Foundations | Months 1-2 | **IN PROGRESS** (Week 5-6 done, Week 7-8 remaining) |
| **Phase 1** | Document Intelligence Layer | Months 3-5 | NOT STARTED |
| **Phase 2** | Agent Layer | Months 6-9 | NOT STARTED |
| **Phase 3** | Reliability Engineering | Months 10-12 | NOT STARTED |
| **Phase 4** | Infrastructure (Cloud) | Months 13-14 | NOT STARTED |

---

## Detailed Progress — Phase 0

### Week 1-2: Production-Grade Python ✅ COMMITTED

**Git commits:** `ffe3ccf` (2026-06-12), `66777fa` (2026-06-15), `2f31cbe` (2026-06-15)

**What was built:**
- Scaffolded the project with `uv` (replaces pip/requirements.txt)
- FastAPI async app with `/health` endpoint
- Strict tooling: `ruff` (linter/formatter), `mypy` (strict=true), `pytest-asyncio`
- Structured JSON logging via `structlog` (replaces print)
- Async test suite with `httpx.AsyncClient`

**Key files:**
- `src/docmind/main.py` — FastAPI entry point with lifespan events
- `src/docmind/core/config.py` — Pydantic Settings (reads `.env`)
- `src/docmind/core/logging.py` — structlog configuration
- `pyproject.toml` — dependency management, ruff/mypy/pytest config
- `tests/test_main.py` — async health check test

---

### Week 2: Docker Infrastructure ✅ COMMITTED

**Git commits:** `5c7d582` (2026-06-22), `0f6a214`, `253f091`

**What was built:**
- `docker-compose.yml` with PostgreSQL (pgvector image) + Redis
- Persistent volumes (`postgres_data`, `redis_data`) so data survives container deletion
- Health checks every 10 seconds on both services
- `.env` / `.env.example` pattern for secrets management
- Fixed Pydantic `extra="ignore"` to skip unrecognized env vars

**Key files:**
- `docker-compose.yml` — PostgreSQL (pgvector) + Redis services
- `.env.example` — template for required env vars
- `.env` — actual secrets (git-ignored)

---

### Week 3-4: FastAPI + API Design ✅ COMMITTED

**Git commits:** `cfa7e71` (2026-07-13), `dcafa3a`, `eee06fe`

**What was built:**
- Full async CRUD API for documents: upload, status check, content retrieval, delete
- Dependency Injection via `api/deps.py` (database sessions + API key auth)
- Background Tasks for async document processing (returns 202 immediately)
- Pydantic v2 response schemas (never leak raw ORM objects)
- SQLAlchemy async ORM with `asyncpg` driver
- Alembic migrations (async-sync bridge via `run_sync`)
- Lifespan events for DB engine startup/shutdown
- Global exception handler (clean JSON errors, no stack traces to clients)
- Integration tests for all endpoints

**Key files:**
- `src/docmind/api/deps.py` — `get_db()` and `verify_api_key()` dependencies
- `src/docmind/api/v1/endpoints/documents.py` — HTTP routes (upload, status, content, delete)
- `src/docmind/api/v1/schemas/document.py` — Pydantic response models
- `src/docmind/db/base.py` — async engine + session factory
- `src/docmind/db/models.py` — SQLAlchemy ORM models
- `alembic/env.py` — async migration bridge
- `alembic/versions/83e4f51fc402_initial_document_schema.py` — first migration
- `tests/test_documents.py` — full endpoint integration tests

**API endpoints (all under `/api/v1/documents`):**
- `POST /upload` — upload document, get job ID back immediately (202)
- `GET /{id}/status` — poll processing status
- `GET /{id}/content` — retrieve processed content
- `DELETE /{id}` — delete document

---

### Week 5-6: PostgreSQL Mastery ⚠️ BUILT BUT NOT COMMITTED

**Status:** All code is written, migration applied to the running DB, EXPLAIN ANALYZE verified. Changes are unstaged in git. Yash has NOT yet written his learnings, so commit is on hold per the workflow rule.

**What was built:**

1. **Full Database Schema** — expanded `models.py` from 1 table to 2:
   - `documents` (parent) — added `metadata_` (JSONB), `chunk_count` (denormalized int)
   - `chunks` (child) — new table with `document_id` FK (CASCADE delete), `chunk_index`, `text`, `embedding` (Vector(1024)), `token_count`, `page_numbers` (ARRAY)
   - One-to-many relationship: `document.chunks` with `cascade="all, delete-orphan"`

2. **Custom Indexes:**
   - `ix_documents_status` — B-tree on `documents.status` (fast filter by processing state)
   - `ix_documents_metadata` — GIN on `documents.metadata_` (search inside JSONB)
   - `ix_chunks_document_id_chunk_index` — Composite B-tree for ordered chunk retrieval per document
   - `ix_chunks_embedding_hnsw` — HNSW vector index for approximate nearest neighbor search (cosine similarity)

3. **Connection Pooling** — configured `create_async_engine` with `pool_size=5`, `max_overflow=10`, `pool_timeout=30`, `pool_pre_ping=True`

4. **Alembic Migration** — `0d5a7cfa563b_add_chunks_table_jsonb_metadata_.py` (enables pgvector extension, creates chunks table, adds indexes)

5. **EXPLAIN ANALYZE Script** — `scripts/explain_queries.py` seeds 100 documents + 1000 chunks with random 1024-dim vectors, then runs 5 query patterns:
   - Primary Key lookup → Index Scan ✅
   - Chunks by document, ordered → Bitmap Index Scan on composite index ✅
   - Filter by status → Index Scan on status index ✅
   - JSONB metadata search → Bitmap Index Scan on GIN index ✅
   - Vector similarity (cosine) → Index Scan on HNSW index ✅

6. **New endpoint:** `GET /documents/{id}/chunks` — retrieve all chunks for a document

7. **Schema updates:** Added `ChunkResponse`, updated `DocumentResponse` with `metadata_` and `chunk_count`

**Uncommitted files:**
- Modified: `pyproject.toml`, `src/docmind/db/models.py`, `src/docmind/db/base.py`, `src/docmind/api/v1/endpoints/documents.py`, `src/docmind/api/v1/schemas/document.py`, `uv.lock`
- New: `alembic/versions/0d5a7cfa563b_*.py`, `scripts/explain_queries.py`, `scripts/explain_output.txt`

---

### Week 7-8: Docker + Local Infrastructure ❌ NOT STARTED

**Roadmap requires:**
- Multi-stage Dockerfiles (development vs production images, layer caching)
- Containerize the FastAPI app itself (currently only DB/Redis are containerized)
- Add Langfuse (self-hosted observability) to docker-compose
- `docker-compose up` should start: FastAPI app + PostgreSQL/pgvector + Redis + Langfuse
- Write a README so anyone can start the full stack with one command

---

## Project Structure

```
e:\DocMind\
├── Docs/
│   └── DocMind.txt              # Master 14-month roadmap
├── alembic/
│   ├── env.py                   # Async-sync bridge for migrations
│   └── versions/
│       ├── 83e4f51fc402_*.py    # Initial documents table (committed)
│       └── 0d5a7cfa563b_*.py    # Chunks + indexes + pgvector (uncommitted)
├── scripts/
│   ├── explain_queries.py       # EXPLAIN ANALYZE script (uncommitted)
│   └── explain_output.txt       # Query plan results (uncommitted)
├── src/docmind/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app with lifespan + exception handler
│   ├── api/
│   │   ├── deps.py              # get_db(), verify_api_key()
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   └── documents.py # CRUD + chunks endpoint
│   │       └── schemas/
│   │           └── document.py  # Pydantic response models
│   ├── core/
│   │   ├── config.py            # Pydantic Settings
│   │   └── logging.py           # structlog config
│   └── db/
│       ├── base.py              # Async engine + session factory + pooling
│       └── models.py            # Document + Chunk ORM models
├── tests/
│   ├── test_main.py             # Health check test
│   └── test_documents.py        # Full endpoint integration tests
├── docker-compose.yml           # PostgreSQL (pgvector) + Redis
├── pyproject.toml               # uv deps, ruff, mypy, pytest config
├── learning_log.md              # Yash's own-words understanding
├── confusion_log.md             # Questions & confusions tracked
├── .env                         # Real secrets (git-ignored)
└── .env.example                 # Secret template for other devs
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.12 | Async, typed, AI ecosystem |
| Framework | FastAPI | Async-native, dependency injection, auto-docs |
| ORM | SQLAlchemy 2.0 (async) | Mapped columns, type-safe, asyncpg driver |
| Database | PostgreSQL + pgvector | Vector search in the same DB, no vendor lock-in |
| Cache | Redis | Session caching, rate limiting (future) |
| Migrations | Alembic | Schema versioning, auto-generate from models |
| Validation | Pydantic v2 | Request/response schemas, settings management |
| Logging | structlog | JSON in production, pretty in development |
| Linting | ruff | Hyper-fast Python linter + formatter |
| Type Check | mypy (strict) | Catches type errors before runtime |
| Testing | pytest + pytest-asyncio | Async test support, httpx for API tests |
| Deps | uv | Deterministic, fast package management |
| Containers | Docker Compose | PostgreSQL + Redis orchestration |

---

## Key Patterns & Decisions

1. **Never commit without learning log entry** — Yash must articulate what he learned in his own words before any git commit.
2. **No paid services** unless explicitly requested (OpenAI, Pinecone, etc.). Use free tiers: Gemini API, Ollama, local sentence-transformers.
3. **All code is async** — blocking the event loop is unacceptable.
4. **All functions have type hints** — `mypy strict=true` enforced.
5. **Response schemas are explicit** — never return raw ORM objects from the API.
6. **B008 (Depends in defaults)** is ignored in ruff — this is idiomatic FastAPI.
7. **Alembic excluded from ruff** — auto-generated migration files have long lines.
8. **`asyncio_default_test_loop_scope = "session"`** in pyproject.toml — prevents the dead-event-loop bug where the SQLAlchemy pool references a destroyed loop.

---

## Immediate Next Steps

1. **Yash writes Week 5-6 learnings** → then commit the unstaged changes
2. **Week 7-8: Containerization** — Multi-stage Dockerfile for FastAPI, add Langfuse to docker-compose
3. After Week 7-8 → Phase 0 is complete → begin Phase 1 (Document Intelligence)
