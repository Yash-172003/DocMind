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
- [ ] **Week 2:** Local Infrastructure
  - Docker Compose for PostgreSQL (with pgvector) and Redis.

## Author

Kanwar Yashwender Singh
