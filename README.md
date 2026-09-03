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

The core stack — the FastAPI app, PostgreSQL (pgvector), and Redis — runs identically on any machine with one command.

1. Copy `.env.example` to `.env` and fill in real values (generate `LANGFUSE_ENCRYPTION_KEY` with `openssl rand -hex 32`, and `LANGFUSE_SALT`/`LANGFUSE_NEXTAUTH_SECRET` with `openssl rand -base64 32` — only needed if you also start Langfuse, see below).
2. Run:

   ```bash
   docker compose up -d --build
   ```

3. Once containers report healthy:

   | Service | URL | Notes |
   |---|---|---|
   | DocMind API | http://localhost:8000 | `/health` for a liveness check, `/docs` for the interactive API docs |
   | PostgreSQL | localhost:5432 | App's own DB (documents, chunks, embeddings) |
   | Redis | localhost:6379 | Reserved for semantic caching (Phase 1) |

Editing anything under `src/` is picked up live — the `app` container runs `uvicorn --reload` with `./src` mounted from the host, no rebuild needed. A rebuild is only required after changing dependencies (`pyproject.toml`/`uv.lock`) or the `Dockerfile` itself.

**Langfuse (self-hosted observability) is opt-in**, not started by default — it's 6 containers (ClickHouse and MinIO included) that isn't wired into the app yet (that's Phase 3), and running it alongside Phase 1's embedding pipeline (PyTorch + sentence-transformers) can exhaust RAM on a 16GB machine. Bring it up separately when you need it:

```bash
docker compose --profile langfuse up -d
```

Then visit http://localhost:3000, logging in with `LANGFUSE_INIT_USER_EMAIL` / `LANGFUSE_INIT_USER_PASSWORD` from `.env` (auto-provisioned on first boot).

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

**Phase 0 Complete** — clean async Python backend, containerized end-to-end, with PostgreSQL, Redis, and a self-hosted Langfuse stack available locally (Langfuse moved behind an opt-in Compose profile in Week 13-14 — see Getting Started above).

**Phase 1 — Document Intelligence Layer** (Months 3-5)

- [x] **Week 9-10:** Document Formats
  - *Completed 2026-08-31*: Built a real extraction pipeline for PDF (`pdfplumber` + `pymupdf` fallback), Word (`python-docx`), and Excel (`openpyxl`), unified behind one `ExtractionResult` shape. Added real file storage so uploads survive to the background processing step. Tested against 5 real invoices, found and fixed a text-scrambling bug (overlapping PDF text blocks) and a bug where extracted tables were computed but never persisted.
- [x] **Week 11-12:** Chunking Strategy
  - *Completed 2026-08-31*: Implemented and compared fixed-size, semantic (TF-cosine similarity), and structural (heading/paragraph-aware) chunking, wired into the pipeline so real `Chunk` rows are now persisted per document. A comparison script against a real 34KB document exposed a CRLF line-ending bug in structural chunking, fixed and regression-tested. Also audited test coverage (84% → 99%), fixing a `coverage.py`/SQLAlchemy-greenlet measurement bug and closing real testing gaps, including one that revealed unreachable dead code.
- [x] **Week 13-14:** Embedding Models
  - *Completed 2026-09-03*: Built a real embedding pipeline (`BAAI/bge-large-en-v1.5` via `sentence-transformers`, CPU-only PyTorch), wired into the pipeline so chunks get real 1024-dim vectors instead of `NULL`. Closed a roadmap gap by adding `section_heading` to chunks. Measuring batch performance found the production model shows almost no CPU speedup from batching (unlike a smaller reference model) — documented honestly rather than assuming the roadmap's general guidance held. Also diagnosed a real memory-exhaustion incident (Docker + PyTorch on a 16GB machine) that initially looked like three unrelated bugs; fixed by moving Langfuse behind an opt-in Compose profile.
- [x] **Week 15-16:** Hybrid Retrieval
  - *Completed 2026-09-03*: Built dense (pgvector HNSW), sparse (hand-rolled BM25 over a new full-text GIN index), Reciprocal Rank Fusion, and cross-encoder reranking, exposed through a new `/api/v1/search` endpoint — DocMind's first question-answering capability. Evaluated all four configurations on 20 real questions (10 exact, 10 semantic): hybrid beat either method alone (95% vs 90%/85% overall), but dense-only scoring 90% on "exact" questions contradicted the roadmap's prediction — investigated and found the real, more nuanced failure mode (a ~0.03 similarity margin on bare identifiers vs ~0.1-0.3+ for genuine topic differences), documented honestly rather than reshaping the test to fit the prediction.

## Author

Kanwar Yashwender Singh
