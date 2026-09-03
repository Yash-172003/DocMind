# DocMind — Project Context

> This file provides complete context for any AI assistant working on this project.
> Last updated: 2026-09-03 (through Phase 1, Week 15-16)

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

## Status

| Phase | Title | Timeline | Status |
|-------|-------|----------|--------|
| **Phase 0** | Engineering Foundations | Months 1-2 | ✅ Complete |
| **Phase 1** | Document Intelligence Layer | Months 3-5 | **IN PROGRESS** — Weeks 9-16 done, Week 17-18 next |
| **Phase 2** | Agent Layer | Months 6-9 | Not started |
| **Phase 3** | Reliability Engineering | Months 10-12 | Not started |
| **Phase 4** | Infrastructure (Cloud) | Months 13-14 | Not started |

Everything below describes the system **as it exists right now** — not a history of how it got here. For the week-by-week history, `README.md`'s "Current Phase" section and `learning_log.md`/`confusion_log.md` have the full record.

---

## Architecture — the pipeline as it stands today

A document's life cycle, end to end:

```
POST /api/v1/documents/upload
        │
        ▼
  save bytes to disk (uploads/{id}/{filename})   ← must happen before the
        │                                          request returns; the
        ▼                                          background task runs after
  BackgroundTask: process_document()
        │
        ├─▶ extraction.router.extract()      → ExtractionResult (text, pages,
        │                                       tables, headings, metadata,
        │                                       warnings) — same shape for
        │                                       every format
        │
        ├─▶ chunking.strategy.chunk_document() → list[TextChunk], using
        │                                        settings.chunking_strategy
        │                                        (default: structural)
        │
        ├─▶ embedding.embedder.Embedder.embed_batch()  → one batch call,
        │                                        1024-dim vectors
        │                                        (BAAI/bge-large-en-v1.5)
        │
        └─▶ persist: Document (content, metadata_, chunk_count) +
                     Chunk rows (text, embedding, token_count,
                     page_numbers, section_heading) — via SQLAlchemy,
                     text_search (tsvector) computed by Postgres itself

GET /api/v1/search?q=...
        │
        ├─▶ dense_search()   — pgvector HNSW, cosine distance
        ├─▶ sparse_search()  — GIN-indexed candidates, hand-rolled BM25 scoring
        ├─▶ reciprocal_rank_fusion()  — merges the two by rank position
        └─▶ Reranker.rerank() (optional, default on) — cross-encoder/
             ms-marco-MiniLM-L-6-v2 re-scores the fused candidates
```

Nothing generates a synthesized answer yet — `/search` returns ranked chunks, not prose. That's Week 17-18.

### Extraction (`src/docmind/extraction/`)
- `router.py` dispatches by file **extension**, not the client's `Content-Type` header (unreliable/spoofable).
- `pdf.py` — `pdfplumber` primary, `pymupdf` fallback. The fallback triggers on **empty text** and, since a real-invoice bug, on **garbled text** too (a heuristic: fraction of extracted tokens ≤2 chars, threshold 0.30 — see Key Decisions).
- `word.py` — `python-docx`; walks the document body in reading order (not paragraphs-then-tables) and reads real `Heading 1`/`Heading 2`/`Title` paragraph styles into `ExtractionResult.headings`.
- `excel.py` — `openpyxl`; each sheet becomes one page and one table.
- `text.py` — trivial UTF-8 decode; raises `CorruptDocumentError` on invalid bytes.
- Every extractor returns the same `ExtractionResult` shape (`models.py`) regardless of format — this is the seam that lets chunking/embedding/retrieval stay format-agnostic.

### Chunking (`src/docmind/chunking/`)
Three interchangeable strategies behind `strategy.chunk_document()`, selected by `settings.chunking_strategy` (`ChunkingStrategy` enum):
- `fixed_size.py` — naive fixed-character windows with overlap. Kept specifically to demonstrate the failure mode (cuts mid-word/mid-sentence), not used in production.
- `semantic.py` — sentence-splits, groups by hand-rolled TF-cosine similarity, breaks early on topic shift.
- `structural.py` — **the default.** Uses real headings (Word) when available, falls back to paragraph boundaries otherwise. Normalizes `\r\n` internally (a real bug found against a Windows-authored file — see Key Decisions). Also the only strategy that populates `section_heading`.
- `tokens.py` — token counts are **approximated** (`len(text) // 4`), not from a real tokenizer — deliberately, to avoid a network-download dependency before an embedding model was chosen. Not yet revisited now that one has been (still open — see Known Gaps).

### Embedding (`src/docmind/embedding/`)
- `embedder.py` — `Embedder(model_name)`, model loading cached by name (`@lru_cache`, since loading ~1.3GB of weights is the expensive part). `embed_batch()` batches (never one-at-a-time) and L2-normalizes output (`normalize_embeddings=True`), matching what the HNSW index's `vector_cosine_ops` expects.
- Production model: `BAAI/bge-large-en-v1.5`, 1024 dimensions (verified empirically — matches `Vector(1024)` set up back in Week 5-6, before this model was chosen). Tests use `all-MiniLM-L6-v2` (384-dim, ~90MB) to avoid downloading the full production model for every test run.
- PyTorch is installed **CPU-only** via a `uv` index override in `pyproject.toml` (`[tool.uv.sources]` / `[[tool.uv.index]]` pointing at `download.pytorch.org/whl/cpu`) — the default PyPI wheel bundles multi-GB CUDA that isn't needed at this scale.

### Retrieval (`src/docmind/retrieval/`)
- `dense.py` — pgvector cosine search via the existing HNSW index.
- `sparse.py` — real, hand-rolled **Okapi BM25** (k1=1.5, b=0.75). Deliberately not Postgres's `ts_rank`/`ts_rank_cd` (different formula) — the GIN-indexed `text_search` tsvector column only finds *candidates* fast; scoring is computed in Python so the algorithm is actually understood, not borrowed. Known imprecision: term frequency is counted from raw regex-tokenized chunk text (no stemming), while the GIN index candidates come from Postgres's stemmed tsvector lexemes — a documented mismatch, not a bug.
- `fusion.py` — Reciprocal Rank Fusion (k=60), combines dense+sparse rankings by rank position, not raw score (the two scores aren't on comparable scales).
- `reranker.py` — `cross-encoder/ms-marco-MiniLM-L-6-v2`, scores (query, chunk) pairs jointly in one forward pass each — more accurate than the bi-encoder embedding model, too slow to run over a whole corpus, so it only reranks hybrid search's already-narrowed candidate set.
- `hybrid.py` — orchestrates all of the above; `reranker=None` gives hybrid-without-rerank.
- Exposed via `GET /api/v1/search` (`q`, `limit`, `document_id`, `rerank` query params).

### Database schema (current)
`documents`: `id`, `filename`, `content_type`, `status` (enum: pending/processing/done/failed), `content` (full extracted text), `error_message`, `metadata_` (JSONB — page_count, author, warnings, tables as raw grids), `chunk_count`, `created_at`, `updated_at`. Indexes: B-tree on `status`, GIN on `metadata_`.

`chunks`: `id`, `document_id` (FK, `ondelete="CASCADE"`), `chunk_index`, `text`, `embedding` (`Vector(1024)`, nullable), `token_count`, `page_numbers` (`ARRAY(Integer)`), `section_heading` (nullable — only structural chunking on Word populates it), `text_search` (`TSVECTOR`, **generated column**, computed by Postgres from `text` on every write), `created_at`. Indexes: composite B-tree on `(document_id, chunk_index)`, HNSW on `embedding` (`vector_cosine_ops`), GIN on `text_search`.

4 migrations applied, in order: `83e4f51fc402` (initial documents table) → `0d5a7cfa563b` (chunks table + JSONB + pgvector) → `523a2792a5ca` (section_heading) → `ad1d1c7c2255` (text_search + GIN).

### API endpoints
All under `/api/v1`, all requiring `X-API-Key` header:
- `POST /documents/upload` — save + queue background processing, 202 immediately
- `GET /documents/{id}/status` — lightweight status poll
- `GET /documents/{id}/content` — full document (content, metadata_, chunk_count)
- `GET /documents/{id}/chunks` — all chunks for a document, ordered
- `DELETE /documents/{id}` — deletes row (cascades to chunks) + uploaded file
- `GET /search` — hybrid retrieval, returns ranked `ScoredChunk[]`

Plus `GET /health` (no auth).

### Infrastructure
`docker-compose.yml` default (`docker compose up -d --build`): `app` (multi-stage Dockerfile, `development` target for local work), `db` (`pgvector/pgvector:pg16`), `redis`. Langfuse (6 services: web, worker, its own Postgres/Redis/ClickHouse/MinIO) is **opt-in** behind `docker compose --profile langfuse up -d` — not wired into the app yet (that's Phase 3 instrumentation), and running it alongside the embedding pipeline exhausted RAM on a 16GB dev machine (see Key Decisions). A named volume (`huggingface_cache`) persists downloaded model weights across container recreates.

### Testing
106 tests (`pytest --cov`), 99% coverage. Every fixture is a real generated file/document, never a mock of extraction/DB behavior — the DB layer is the real dev Postgres throughout, no test database isolation. `[tool.coverage.run] concurrency = ["greenlet", "thread"]` is required for accurate numbers (SQLAlchemy's async engine bridges to its sync driver via greenlet switches that `coverage.py` doesn't follow by default — see Key Decisions).

---

## Key Decisions & Why (Week 5-6 through 15-16)

- **JSONB for document metadata, not fixed columns** — different formats produce different metadata shapes; GIN-indexed JSONB avoids a column per possible field.
- **HNSW over IVFFlat for the vector index** — works well from the first insert (no training step), better recall, at the cost of more memory — acceptable at this scale.
- **Connection pooling tuned explicitly** (`pool_size=5, max_overflow=10, pool_pre_ping=True`) rather than left default.
- **Unified `ExtractionResult` shape across all formats** — the single most load-bearing design decision in the whole pipeline; chunking/embedding/retrieval never need to know what format a document started as.
- **PDF fallback (`pymupdf`) triggers on garbled text, not just empty text** — found via 5 real invoices: two TallyPrime-exported ones had non-empty but scrambled text (overlapping text blocks confusing `pdfplumber`'s line reconstruction). The garbling heuristic (≤2-char-token fraction ≥0.30) was tuned against those real files; a synthetic reproduction attempt for automated testing was explicitly abandoned as unreliable (documented in `confusion_log.md`) — validated against the real files instead.
- **`Unstructured` library skipped** despite being named in the roadmap — its PDF/text partitioning downloads NLTK data over the network on first use, which would make the test suite depend on internet access.
- **Structural chunking is the production default**, not semantic or fixed-size — best preserves real document structure when available (headings), falls back gracefully to paragraphs otherwise.
- **Extracted tables are persisted as raw grids in `metadata_["tables"]`**, never flattened into `content` — a real bug (found via manual testing) had them computed but silently discarded; column alignment matters for future consumers (e.g. the Phase 2 invoice audit agent) that need real rows, not reflowed prose.
- **Token counts are a `len(text)//4` approximation**, not a real tokenizer — avoiding a network-dependent tokenizer download before an embedding model was chosen (Week 11-12). Still true even after Week 13-14 picked `bge-large-en-v1.5` — worth revisiting (see Known Gaps).
- **BM25 hand-rolled instead of using Postgres's `ts_rank`** — the point of this week's Okapi BM25 paper reading was understanding the algorithm, not calling a library; the GIN index is used for fast candidate retrieval only.
- **RRF fuses by rank position, not raw score** — dense (cosine similarity) and sparse (BM25) scores are on incomparable scales.
- **CPU-only PyTorch via a `uv` index override** — the default PyPI wheel bundles multi-GB CUDA support not needed at this project's scale.
- **Langfuse moved behind an opt-in Compose profile** (`profiles: ["langfuse"]`) — running its 6 containers (ClickHouse/MinIO especially) alongside the embedding pipeline exhausted RAM (down to 0.62GB free of 15.24GB) on the actual dev machine, surfacing as three different-looking failures before the real cause was found. Langfuse isn't wired into the app yet anyway (Phase 3), so nothing is lost by deferring it.
- **`concurrency = ["greenlet", "thread"]` in `[tool.coverage.run]`** — without it, `coverage.py` silently under-reports every route handler that awaits a DB call (SQLAlchemy's async-to-sync bridge uses greenlets, which the default tracer doesn't follow). First measurement showed 84% with `documents.py` at a false 37%; fixed measurement showed 93% and `documents.py` at a real 88%.
- **Standalone scripts (`scripts/*.py`) insert `src` onto `sys.path` manually** — there's no `[build-system]` in `pyproject.toml`, so `docmind` is never actually installed as a package; only pytest's `pythonpath = ["src"]` and each script's own `sys.path.insert()` make imports resolve. Alembic commands need `PYTHONPATH=src` prefixed for the same reason.

---

## Tried and Rejected

- **Postgres's native `ts_rank`/`ts_rank_cd`** for sparse scoring — works, but isn't BM25; rejected in favor of hand-rolling the real algorithm (see Key Decisions).
- **Pinning `transformers<5.0`** to dodge a Windows-specific native crash in its newer threaded model-loading path — blocked outright: `sentence-transformers>=6.0.1` requires `transformers>=5.0.0,<6.0.0`, so this was never installable.
- **`HF_DEACTIVATE_ASYNC_LOAD=1`** as a fix for that same crash (a real, documented env var for disabling `transformers`' threaded checkpoint loading) — tried, crash reproduced identically. The real cause was system memory exhaustion (0.62GB free), not the threading path; the env var was chasing the wrong hypothesis.
- **Synthetic PDF fixtures to reproduce the garbling bug for an automated test** — multiple attempts to recreate the exact character-interleaving statistics via `pymupdf`-drawn overlapping text never crossed the tuned detection threshold (real files scored 0.39-0.40 short-token ratio; synthetic attempts topped out at 0.14-0.24). Abandoned in favor of a direct unit test of the heuristic function using the actual garbled text, plus manual validation against the real files.
- **Azure Document Intelligence integration** — named in the roadmap as leveraging Yash's existing strength, but never implemented: requires a real Azure subscription/API key that wasn't provisioned, and building a "comparison" without real credentials would be theater. Explicitly deferred, not forgotten.
- **Excel/Word extraction robustness testing against real-world files** — only PDF got the "find real bugs" treatment (5 real invoices). DOCX/XLSX extractors have only ever been tested against files this project's own test suite generated (`python-docx`/`openpyxl` building their own fixtures) — a real, acknowledged gap, explicitly excluded from a coverage-audit pass at Yash's request pending a real file being available.

---

## Known Gaps / Documented Limitations

- **PDF and Excel/plain-text have no heading detection** — structural chunking always falls back to paragraph boundaries for them. Word is the only format with real structural signal.
- **Token counting is still `len(text)//4`**, not `bge-large-en-v1.5`'s actual tokenizer, even though that model is now the committed choice.
- **BM25's term-frequency tokenization doesn't match the GIN index's stemming** (raw regex words vs. Postgres's stemmed lexemes) — candidates can be found via a stem match but under-counted during scoring.
- **Dense retrieval is fragile (not immune) on bare identifiers** — measured directly: two chunks differing only by one digit sequence separate by only ~0.03 cosine similarity, versus ~0.1-0.3+ for genuinely different topics. Real in isolation, but a margin that thin would likely lose to an unrelated-but-broadly-similar chunk in a larger corpus.
- **`pdf.py`'s garbled/empty-recovery branches sit at 88% coverage**, intentionally — validated against real invoices, not a synthetic test (see Tried and Rejected).
- **No LLM API has been called anywhere in the codebase yet.** Everything through Week 15-16 is extraction, chunking, embedding, and retrieval — all local/free. Week 17-18 is the first point a generative model (Gemini, per the roadmap's cost plan) enters the system at all.

---

## What Week 17-18 (RAG Generation) Needs to Pick Up

Per `Docs/DocMind.txt`: prompt design with `[1]`, `[2]` source markers instructing the model to cite every claim; citation grounding (parse the response, extract citations, link back to source passages); faithfulness enforcement (the model must say "not in documents" rather than fabricate); and handling contradicting sources across documents.

Concretely, this needs:
1. **A first LLM API integration** — nothing calls an external LLM yet. The roadmap's cost plan specifies the Gemini API (free tier, 1,500 req/day) as primary, with Groq as a backup.
2. **Consuming `/search`'s `ScoredChunk[]` output** as the context fed into that prompt — the retrieval layer already returns exactly the ranked, scored chunks (with `document_id`, `chunk_index`, `page_numbers`) a citation needs to point back to.
3. A new response shape distinct from `ScoredChunk` — probably an answer string plus a list of citations, each resolving back to a specific chunk.

---

## Project Structure

```
e:\DocMind\
├── Docs/
│   └── DocMind.txt                    # Master 14-month roadmap
├── alembic/
│   ├── env.py                         # Async-sync bridge for migrations
│   └── versions/                      # 4 migrations, see Database schema above
├── scripts/                           # One-off measurement/comparison scripts (not part of the app)
│   ├── explain_queries.py             # Week 5-6: EXPLAIN ANALYZE on 5 query patterns
│   ├── compare_chunking.py            # Week 11-12: fixed/semantic/structural comparison
│   ├── measure_embedding_batching.py  # Week 13-14: batching speedup measurement
│   └── evaluate_retrieval.py          # Week 15-16: 20-question dense/sparse/hybrid eval
├── src/docmind/
│   ├── main.py                        # FastAPI app, lifespan, global exception handler
│   ├── api/
│   │   ├── deps.py                    # get_db(), verify_api_key()
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── documents.py       # Upload/status/content/chunks/delete + process_document()
│   │       │   └── search.py          # Hybrid search endpoint
│   │       └── schemas/document.py    # Pydantic response models
│   ├── core/
│   │   ├── config.py                  # Settings (chunking/embedding/reranker model choices)
│   │   ├── logging.py                 # structlog config
│   │   └── storage.py                 # Local disk upload storage
│   ├── db/
│   │   ├── base.py                    # Async engine + session factory + pooling
│   │   └── models.py                  # Document + Chunk ORM models
│   ├── extraction/                    # router, pdf, word, excel, text, models, exceptions
│   ├── chunking/                      # strategy, fixed_size, semantic, structural, tokens, models
│   ├── embedding/                     # embedder.py (Embedder class, model caching)
│   └── retrieval/                     # dense, sparse, fusion, reranker, hybrid, models
├── tests/                             # 106 tests, mirrors src/ structure, 99% coverage
├── docker-compose.yml                 # app + db + redis by default; langfuse behind --profile
├── Dockerfile                         # multi-stage: development / production targets
├── pyproject.toml                     # uv deps, ruff, mypy, pytest, coverage, uv CPU-torch index
├── learning_log.md                    # Yash's own-words understanding, one entry per week
├── confusion_log.md                   # Real bugs/surprises found, written by Claude
├── .env                                # Real secrets (git-ignored)
└── .env.example                        # Secret template
```

---

## Key Patterns & Decisions (standing rules)

1. **Never commit without a learning log entry** — Yash writes what he learned in his own words (spelling/grammar corrected, voice preserved) before any commit. Claude writes `confusion_log.md` entries for real bugs/surprises found along the way, in the same commit.
2. **A matching checkbox entry goes into `README.md`'s "Current Phase" section every time**, alongside the learning log — not optional, done automatically.
3. **No paid services** unless explicitly requested. Free tiers/local only: Gemini API, Ollama, local `sentence-transformers`, self-hosted Langfuse.
4. **All code is async**; blocking the event loop is unacceptable.
5. **All functions have type hints**; `mypy strict=true` enforced, zero errors maintained.
6. **Response schemas are explicit** — never return raw ORM objects from the API.
7. **Real fixtures over mocks** — tests generate real PDFs/DOCX/XLSX via the same libraries production code uses, and hit the real dev Postgres; nothing about extraction, chunking, or the DB layer is mocked.
8. **When a measured result contradicts a prediction (the roadmap's or a design assumption), investigate and report honestly** — don't reshape the test until the numbers match, and don't quietly bury the discrepancy. Several of the entries in Key Decisions above exist because of this.
9. **`B008` (Depends in defaults) ignored in ruff** — idiomatic FastAPI. **Alembic excluded from ruff** — auto-generated files have long lines. **`asyncio_default_test_loop_scope = "session"`** — prevents a dead-event-loop bug in the SQLAlchemy pool.
10. Before running host-side tests that load heavy ML models (`bge-large`, the cross-encoder), stop the `app` Docker container first if memory is tight — both would otherwise load separate copies of the same models simultaneously.
