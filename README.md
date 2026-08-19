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

## Author

Kanwar Yashwender Singh
