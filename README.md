# DocMind

**Enterprise Document Intelligence Platform**

Built end-to-end over 14 months as a deep engineering learning project.

## What DocMind Will Be

- Ingests any enterprise document: PDF, Word, Excel, email, HTML
- Extracts structured knowledge with citation grounding
- Runs autonomous multi-step audit and analysis workflows
- Exposes an MCP server usable by any AI client
- Monitors itself for quality, cost, and hallucination rate

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 with full type hints |
| API | FastAPI |
| Database | PostgreSQL + pgvector |
| Cache | Redis |
| Local Infra | Docker Compose |
| Agents | LangGraph |
| Embeddings | sentence-transformers (BAAI/bge-large-en-v1.5) |
| LLM | Gemini API (free tier) |
| Observability | Langfuse (self-hosted) |

## Getting Started

The entire stack — the FastAPI app, PostgreSQL (pgvector), Redis, and a self-hosted Langfuse observability stack — runs identically on any machine with one command.

1. Copy `.env.example` to `.env` and fill in real values (generate `LANGFUSE_ENCRYPTION_KEY` with `openssl rand -hex 32`, and `LANGFUSE_SALT`/`LANGFUSE_NEXTAUTH_SECRET` with `openssl rand -base64 32`).
2. Run:

   ```bash
   docker compose up -d --build
   ```

3. Once containers report healthy:

   | Service | URL | Notes |
   |---|---|---|
   | DocMind API | http://localhost:8000 | `/health` for a liveness check, `/docs` for the interactive API docs |
   | Langfuse | http://localhost:3000 | Log in with `LANGFUSE_INIT_USER_EMAIL` / `LANGFUSE_INIT_USER_PASSWORD` from `.env` — auto-provisioned on first boot |
   | PostgreSQL | localhost:5432 | App's own DB (documents, chunks) |
   | Redis | localhost:6379 | Reserved for semantic caching (Phase 1) |

Editing anything under `src/` is picked up live — the `app` container runs `uvicorn --reload` with `./src` mounted from the host, no rebuild needed. A rebuild is only required after changing dependencies (`pyproject.toml`/`uv.lock`) or the `Dockerfile` itself.

To stop everything: `docker compose down` (add `-v` to also wipe all volumes/data).

## Current Phase

**Phase 0 — Engineering Foundations** (Months 1-2)

- [x] **Week 1:** Production-grade Python — async, typed, tested, logged.
  - *Completed 2026-06-15*: Scaffolding with `uv`, FastAPI, strict `mypy`, `ruff`, `pytest-asyncio`, and `structlog`.
- [x] **Week 2:** Local Infrastructure
  - *Completed 2026-06-22*: Docker Compose with PostgreSQL (pgvector) and Redis, persistent volumes, health checks, and `.env` secret management.
- [x] **Week 3-4:** FastAPI + API Design
  - *Completed 2026-07-10*: Built a production-grade async FastAPI architecture with SQLAlchemy, Alembic, Dependency Injection, API key authentication, Pydantic v2 schemas, background task processing, lifespan events, exception handling, and integration tests for document workflows.
- [x] **Week 5-6:** PostgreSQL Mastery
  - *Completed 2026-08-19*: Added a `chunks` table with pgvector embeddings, JSONB metadata on documents, four purpose-built indexes (status B-tree, metadata GIN, composite chunk lookup, HNSW vector search), and connection pooling. Verified index usage with an EXPLAIN ANALYZE script against 1000 seeded chunks.
- [x] **Week 7-8:** Docker + Local Infrastructure
  - *Completed 2026-08-19*: Containerized the FastAPI app with a multi-stage Dockerfile (dev/production targets), added it to `docker-compose.yml`, and added a full self-hosted Langfuse observability stack (web, worker, its own Postgres/Redis/ClickHouse/MinIO). One command now starts the entire local environment.

**Phase 0 Complete** — clean async Python backend, containerized end-to-end, with PostgreSQL, Redis, and Langfuse all running locally behind one `docker compose up`.

**Phase 1 — Document Intelligence Layer** (Months 3-5)

- [x] **Week 9-10:** Document Formats
  - *Completed 2026-08-31*: Built a real extraction pipeline for PDF (`pdfplumber` + `pymupdf` fallback), Word (`python-docx`), and Excel (`openpyxl`), unified behind one `ExtractionResult` shape. Added real file storage so uploads survive to the background processing step. Tested against 5 real invoices, found and fixed a text-scrambling bug (overlapping PDF text blocks) and a bug where extracted tables were computed but never persisted.

## Author

Kanwar Yashwender Singh
