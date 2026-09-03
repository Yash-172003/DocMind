# CLAUDE.md

## Stack
Python 3.12 · FastAPI · SQLAlchemy 2.0 (async, `asyncpg`) · PostgreSQL 16 + `pgvector` · Redis · Alembic · Pydantic v2 · `structlog` · `uv` (deps) · `ruff` · `mypy --strict` · `pytest` + `pytest-asyncio` + `pytest-cov` · Docker Compose. Document intelligence: `pdfplumber`/`pymupdf`, `python-docx`, `openpyxl`. ML: `sentence-transformers` (`BAAI/bge-large-en-v1.5` embeddings, `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker), PyTorch **CPU-only** (see Gotchas).

## Tests
```
uv run pytest                                          # full suite
uv run pytest --cov=docmind --cov-report=term-missing  # with coverage (target: ~99%)
uv run ruff check .                                    # lint
uv run mypy src                                        # types, strict
```
Needs `db`/`redis` up (`docker compose up -d db redis`). Every fixture is a real generated file/document hitting the real dev Postgres — nothing is mocked. If free RAM is tight, `docker compose stop app` before running tests that load `bge-large`/the cross-encoder — the container and the host test process would otherwise each load a separate multi-GB copy.

## Docker Services
```
docker compose up -d --build              # app + db + redis (the default, lean stack)
docker compose --profile langfuse up -d   # + Langfuse (web/worker/its own pg/redis/clickhouse/minio)
docker compose down                       # stop (add -v to also wipe volumes)
```
Langfuse is opt-in, not wired into the app yet (Phase 3 work) — see Gotchas for why it's excluded by default.

## Migrations
```
PYTHONPATH=src uv run alembic revision --autogenerate -m "message"
PYTHONPATH=src uv run alembic upgrade head
```
`PYTHONPATH=src` is required for every Alembic invocation — see Gotchas.

## Conventions
- Everything async; never block the event loop.
- Type hints mandatory; `mypy --strict` passes with zero errors — keep it that way.
- API responses are explicit Pydantic schemas, never raw ORM objects.
- Every extractor returns the same `ExtractionResult` shape regardless of source format (PDF/Word/Excel/text) — chunking/embedding/retrieval never branch on format.
- Prefer hand-rolling an algorithm you're meant to be learning (BM25, TF-cosine similarity) over reaching for a library or Postgres's built-in equivalent, when the point of the exercise is understanding it.
- `ruff` ignores `B008` (FastAPI `Depends()` in defaults is idiomatic) and excludes `alembic/` (generated files, long lines).
- When a measured result contradicts an assumption (roadmap's or your own), investigate and report the real finding — don't reshape the test to match the prediction.
- Workflow before any commit: Yash writes a `learning_log.md` entry in his own words; real bugs/surprises get a `confusion_log.md` entry; `README.md`'s "Current Phase" gets a matching checkbox. All in the same commit.

## Gotchas
- **No `[build-system]` in `pyproject.toml`** — `docmind` is never installed as a package. Only pytest's `pythonpath = ["src"]` makes imports resolve for tests; standalone scripts (`scripts/*.py`) must `sys.path.insert()` `src` themselves, and Alembic needs `PYTHONPATH=src` on every call.
- **`coverage.py` under-reports async DB code by default** — SQLAlchemy's async engine bridges to its sync driver via greenlet switches the tracer doesn't follow unless `[tool.coverage.run] concurrency = ["greenlet", "thread"]` is set (already is). Without it, route handlers can show ~37% covered while actually near 100%.
- **Postgres `AVG()` returns `NUMERIC`** → `asyncpg`/SQLAlchemy surfaces it as `decimal.Decimal`, not `float`. Mixing it into float arithmetic raises `TypeError` — convert explicitly.
- **PyPI's default `torch` wheel bundles multi-GB CUDA.** CPU-only is pulled via a `uv` index override in `pyproject.toml` (`[tool.uv.sources]` / `[[tool.uv.index]]`) — don't remove it without meaning to.
- **Docker Desktop's WSL2 VM does not release memory when containers stop** — `docker compose stop` alone can leave RAM exhausted; `wsl --shutdown` actually reclaims it (Docker restarts the VM automatically on next use).
- **A crash that survives a targeted fix means the fix was aimed at the wrong cause.** (`HF_DEACTIVATE_ASYNC_LOAD=1` didn't stop a native model-loading crash — the real cause was system memory exhaustion, not threaded loading.)

@CONTEXT.md
