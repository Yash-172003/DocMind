# Learning Log

This file is a personal record of understanding. It captures my thoughts and takeaways in my own words at the moment of building.

---

## 2026-06-12 — Phase 0, Week 1

**What I built:** Scaffolded production-grade Python backend with uv, FastAPI, and strict typing

**What I learned:** From what I have understood, we have created multiple files here. The `main.py` file holds the main engine, where we have our FastAPI build. Also, we have our `pyproject.toml` file, which is like the backbone structure or blueprint of our application. It replaces the old `requirements.txt` file. So, it tells Python the dependencies we need, and `uv` is the tool which helps us read the blueprint and download them, which is much faster than the pip method. Now, we also have `ruff`, which is the Python formatter and linter that helps us with how the code looks and fixes errors/bugs automatically. It also has a dead code utility feature and a syntax modernizer too. We have `mypy` too, which helps us enforce fixed static type hints by checking them in our code. Now, we also have our `tests` folder which has the `test_main.py` file. It basically contains tests to check the health of the FastAPI app, as it is asynchronous and normal testing won't work.

---

## 2026-06-15 — Phase 0, Week 1

**What I built:** Implemented structured JSON logging via structlog

**What I learned:** For the things I understood about `structlog`, we have replaced normal "print" statements because normally it will become impossible for us to query the outputs if they are flat strings. So, we use `structlog` so we can instantly query it. It gives us timestamps, log levels, and also helps the output to be in JSON format on the server and a nice display for the user.

---

## 2026-06-22 — Phase 0, Week 2

**What I built:** Docker Compose infrastructure with PostgreSQL (pgvector) and Redis

**What I learned:** We created a `docker-compose.yml` file with two things. First, the `db` service which includes PostgreSQL and pgvector. This is for the storage of our embeddings so that we can search them semantically. It also has a volume called `postgres_data` which helps to save our data to a virtual disk. The important thing is that the data survives even if the container is deleted entirely — without a volume, if we stop Docker, the data is gone forever. It also runs a health check every 10 seconds. Second, the `redis` service is the cache part of our system. We enforced password authentication with it, and it has the same volume and health check pattern.

We also created two files: `.env.example` which stores the template of required variables, and `.env` which stores the actual passwords. The `.env` file is git-ignored, so real passwords are never committed to version history. `.env.example` exists as the way to tell other developers which variables they need to set up without exposing real secrets.

We also ran into an error because Pydantic was being strict about what it accepts — the new variables in `.env` like `POSTGRES_USER` didn't have matching fields in the `Settings` class, so it rejected them. We fixed this by adding `extra="ignore"` to tell Pydantic to silently skip variables it doesn't recognize rather than crashing the whole app.

---

## 2026-07-10 — Phase 0, Week 3-4

**What I built:** A production-grade async FastAPI architecture with SQLAlchemy, Alembic, Dependency Injection, and Background Tasks.

**What I learned:** 
We updated our `config.py` file which added `database_url` and `api_key` to the Pydantic Settings class cause hardcoding it in our code is a security risk. So this file reads the `.env` file and checks if the variables are missing or wrong and crash the app immediately.

Now, we also created the `base.py` file which acts as the bridge between our FastAPI app and PostgreSQL. It has the `create_async_engine` which is the actual connection to the PostgreSQL. It also has `async_sessionmaker` which helps us create a session for each API call.

We created `models.py` too which defines what our db tables are gonna look like. It uses SQLAlchemy which is the translator between the python code and the sql db and allows us to create python object and classes instead of sql strings. This is what ORM means - Object Relational Mapping. Every table created will inherit from the Base class. We also have the `DocumentStatus` class which has defined 4 states - pending, processing, done, failed. We also have the `Document` class which basically gets the filename, uuid, status, created_at, updated_at etc.

We have created `env.py` which has Alembic. It is a db migration tool. So, basically `models.py` is like a blueprint and Alembic is the one who reads the blueprint and builds and modifies the actual db. Let's say we altered a Python class (like adding a new column), Alembic detects the difference between the code and the live db and then automatically generates the Python migration scripts required to update the db schema. For our project it compares by checking what's in `Base.metadata` and PostgreSQL. One of the core problems this file solves is that Alembic is built for synchronous SQLAlchemy and our app is async. So, it bridges this gap. `connection.run_sync(do_run_migrations)` is the bridge. It takes the synchronous migration function and runs it through the async connection. We can think of it as an adapter - async engine on one side, sync migration code on the other, `run_sync` in the middle making them compatible. It can also run in two modes - offline and online too.

Now, we also have `deps.py` which defines two things our FastAPI endpoints will need on almost every request - a db session and authentication. We are using dependency injection and it is a very important concept too. FastAPI sees the `Depends(get_db)` and `Depends(verify_api_key)`, and runs those functions automatically before any endpoint even starts. The `get_db` function is a thin wrapper around `get_async_session` for testability for when we write tests for later. In the `verify_api_key` function we are using `Security()` which works like `Depends()` but is security-related. And then its just simple logic, if the header is missing — api_key is None — reject. If it does not match your configured key in `.env` — reject. Otherwise return the key and let the request continue.

We also have `document.py` in the schema folder which basically defines our response model. We dont want to return raw ORM models from our API but instead want to define a explicit response that has a fixed schema.

We have `documents.py` in the endpoints folder which contains the actual HTTP routes for our app - our real API. So, the user can upload a doc and immediately get a job id back, and then can poll for the status while processing happens in the bg. The four concepts here used are - 1) Models from `models.py` 2) Sessions from `deps.py` 3) Dependency injection from `deps.py` 4) Async bg tasks. The `simulate_document_processing` function with `asyncio.sleep(3)` is a placeholder — Phase 1 replaces it with real PDF extraction.

In the `main.py` file, we added lifespan event which ensures clean startup and close ups of the db engine. We also added a global_exception_handler to handdle any random python error and officially mounted the router for our document endpoints.

In the `test_documents.py` file, we simulated a client uploading a fake file, checking the status, reading and then deleting the content too. This serves as an integration test to see if everything works together perfectly fine.

Now we also encountered a asyncio error too. What happened is:

```text
event loop      (all async operations)
      ↑
connected (created by)
      ↑
async engine → "pool of connections" to PostgreSQL
      └─ (pre-opened connections)

But, pytest-asyncio → new event loop for each test

So:

async engine
      ↓
created by event loop
      ↓
shared across tests
      ↓
event loop from test 1 was destroyed
      ↓
test 2 inherited an engine pointing to a dead loop
```

So, for the fix: setting `asyncio_default_test_loop_scope = "session"` gives all tests one shared loop so the pool stays alive and valid throughout.

---

## 2026-08-19 — Phase 0, Week 5-6

**What I built:** Expanded the database schema with a `chunks` table, JSONB metadata, pgvector embeddings, four custom indexes, connection pooling, and verified everything with EXPLAIN ANALYZE.

**What I learned:**

From what I have understood, earlier our `Document` table was only storing information about the document itself, but now it can support chunking, embeddings, and metadata filtering.

In `models.py`, we added two new fields to the `Document` model. The first one is `metadata_`. Some files may have page counts, authors, languages, file sizes, and other files may have completely different information. Instead of creating a new database column for every possible property, JSONB lets us store all of that in a schema-less format. We also added `chunk_count`, storing the value directly in the document row so we can read it instantly without doing extra joins or running a `COUNT(*)` query every time.

We also created a completely new `Chunk` table. From what I understood, this is where the real content of our documents lives. Every chunk belongs to one document through the `document_id` foreign key. We also enabled `ondelete="CASCADE"`, which means if a document gets deleted, PostgreSQL automatically deletes all its chunks too, without us having to manually clean them up. The `chunk_index` tells us the order of the chunk inside the document. The `text` column stores the extracted content itself. We also added `token_count` and `page_numbers` to the chunk model.

Now, we also created a relationship called `document.chunks`. This is a one-to-many relationship because one document can have many chunks. We configured it with `cascade="all, delete-orphan"`, and from what I understood, while PostgreSQL handles deletes at the database level through the foreign key, SQLAlchemy can also automatically manage related chunk objects when operations happen through the ORM. Basically, both the database and the Python layer are working together to keep the data clean and synchronized.

Another thing we did was create multiple indexes. Before this, I mostly thought indexes were just used to make queries faster, but here I learned that different index types solve completely different query patterns. The status index helps queries like finding all completed documents. The composite index on `document_id` and `chunk_index` is interesting because it can satisfy both filtering and sorting from a single index. Finally, the HNSW index is specifically designed for vector similarity search.

In `base.py`, we improved our database connection pooling, and what I learned is that creating a new database connection every time an API request arrives is expensive. So SQLAlchemy maintains a pool of reusable connections. We set `pool_size=5`, which means five connections stay ready at all times. `max_overflow=10` allows temporary extra connections during heavy traffic, bringing the maximum to fifteen. `pool_timeout=30` tells requests to wait up to thirty seconds before failing if every connection is busy.

In `document.py`, we updated our response schemas. The `DocumentResponse` model now exposes the new `metadata_` and `chunk_count` fields. We also created a new `ChunkResponse` model.

We also added a new endpoint called `GET /documents/{id}/chunks`.

We also created a standalone script called `explain_queries.py`. This was mainly used to verify that PostgreSQL was actually using the indexes we designed. The script generated 100 documents and 1000 chunks with random 1024-dimensional vectors and then ran `EXPLAIN ANALYZE` on different query patterns. From what I understood, this is an important validation step because creating an index does not automatically mean PostgreSQL will use it.

Finally, we updated `pyproject.toml`. We added `numpy` and `pgvector` because they are required for vector-related operations.

---

## 2026-08-19 — Phase 0, Week 7-8

**What I built:** Containerized the FastAPI app itself with a multi-stage Dockerfile, added it to docker-compose, and added a full self-hosted Langfuse observability stack.

**What I learned:**

The biggest thing I learned was how a multi-stage Docker build works. We created a common base stage which acts as the foundation for both development and production environments. One important optimization here is that Docker caches layers. As long as dependencies remain unchanged, it simply reuses the cached layer.

We also fixed the import issue inside Docker by setting `PYTHONPATH=/app/src`. Since our project is not actually installed as a Python package inside the container, Python needs to be explicitly told where the `docmind` package exists.

We then created two separate environments. The development stage installs all development tools, allowing code changes on our machine to instantly reflect inside the container. The production stage only installs what is needed to run the application and excludes development dependencies.

We also created a `.dockerignore` file to prevent unnecessary files and sensitive information from being sent into the Docker build process.

In `docker-compose.yml`, we added a new `app` service which builds the development version of the Docker image. One important thing I learned is that containers communicate using service names rather than `localhost`. This is why the application uses `db:5432` to connect to PostgreSQL when running inside Docker. We also configured health checks so the application waits until PostgreSQL and Redis are actually ready before starting.

Another major addition was the complete Langfuse stack, and it consists of multiple services working together. It has its own web application, worker service, PostgreSQL database, Redis queue, ClickHouse analytics database, and MinIO object storage. Each component has a specific responsibility, and keeping them separate avoids conflicts with our own application infrastructure.

We also configured persistent volumes for all major services. From what I understood, these volumes act like virtual disks that survive container restarts, ensuring that databases and application data are not lost whenever containers are recreated.

Finally, we encountered an issue with ClickHouse. The application kept crashing because Langfuse automatically assumed a clustered ClickHouse setup when a specific configuration variable was missing. Cluster mode requires Zookeeper, which we were not running. The fix was to explicitly disable cluster mode, which allowed ClickHouse to run as a standalone instance. This taught me that some configuration flags may look optional but can completely change how a system behaves internally.

---

## 2026-08-31 — Phase 1, Week 9-10

**What I built:** A real document extraction pipeline for PDF, Word, and Excel files — real file storage, a unified extraction module, and error handling that survives corrupt/unsupported files instead of crashing. Found and fixed two real bugs by testing against real invoices.

**What I learned:**

When I reviewed the existing upload flow, I noticed that although the API was receiving the file, it was only reading information like the filename and content type. The actual file contents were being discarded, and the background task was simply simulating work with an `asyncio.sleep`. This meant there was nothing available for extraction later. So before building any extraction logic, we had to solve the file storage problem first.

We created a new `storage.py` module which is responsible for saving, reading, and deleting uploaded files. One important thing I learned is that uploaded file streams only exist during the request itself. Once the request finishes, the stream disappears. Because of that, we must save the file immediately inside the request handler before sending the response back. Otherwise, the background task would have nothing to process later. For now, files are stored on local disk, but this is mainly a temporary solution until object storage is introduced in future phases.

We also built an entire extraction module to handle different document formats. Instead of writing completely different processing flows for PDFs, Word files, Excel files, and text files, we created a common `ExtractionResult` model. No matter which file type is processed, the rest of the application receives the same structure containing extracted text, metadata, tables, warnings, and page information.

For PDF extraction, we primarily use `pdfplumber` and fall back to `pymupdf` when necessary. Word files are processed in a way that preserves the original document order, including both paragraphs and tables. Excel files are handled sheet by sheet, with each sheet contributing both text and structured table data. We also created a router which selects the correct extractor based on file extension. What I learned here is that file extensions are generally more reliable than HTTP headers because headers can be incorrect or manipulated.

We then rewired the document processing workflow itself. The upload endpoint now saves the uploaded file before queuing background work. The old fake processing function was replaced with a real processing pipeline that reads the file back from storage, extracts its contents, stores the extracted information, and updates the document status. We also improved error handling so extraction failures mark the document as failed instead of crashing the background task entirely.

Another thing I learned was how important dependency selection can be. We added libraries specifically designed for handling PDFs, Word documents, and Excel files. However, we intentionally avoided the Unstructured library even though it appeared in the roadmap. The reason was that it introduces network-dependent behavior by downloading NLP resources on first use. This would make tests unreliable because they would depend on internet access. So the decision was not just about functionality but also about maintaining a stable and reproducible testing environment.

A major focus of this phase was testing. The test suite grew significantly, and instead of using fake or mocked files, every test generates real PDFs, Word documents, and Excel files using the same libraries used in production. From what I understood, this makes the tests much more realistic because they validate the actual extraction logic rather than artificial scenarios.

The most interesting thing I learned came from testing against real invoices. We processed five actual invoices and discovered that two of them produced heavily scrambled text. The extraction was not failing completely, which is why our fallback mechanism never activated. The text existed, but it was clearly corrupted. After investigating, we found that the PDF generator used by those invoices positioned multiple text blocks at overlapping coordinates, causing the extractor to interleave characters incorrectly.

To solve this, we created a heuristic that measures how much of the extracted text consists of extremely short words. Clean documents stayed within one range while the corrupted invoices had significantly higher scores. We then used this heuristic to automatically detect garbled text and trigger the fallback extraction path. After reprocessing the problematic invoices, both extracted correctly. What I learned from this is that failures are not always obvious. Sometimes a system technically succeeds but still produces unusable results, so we need validation checks beyond simply asking whether extraction completed.

We also discovered another genuine bug while testing through the API. Although the extractors were correctly identifying tables, that table data was never being saved anywhere. The processing pipeline was only storing text and metadata, silently discarding the extracted tables. This explained why invoices appeared to lose their structured line-item information even though extraction itself was working correctly. The fix was to persist the tables into the document metadata before returning the response. After re-testing with a real invoice, all tables appeared correctly through the API with their column structure preserved.

Overall, the biggest takeaway from this phase is that document extraction is much more than just parsing files. We had to solve file persistence, build a standardized extraction pipeline, handle multiple formats, improve error recovery, validate extraction quality using real documents, and ensure structured information such as tables survives all the way from extraction to the API response.

---

## 2026-08-31 — Phase 1, Week 11-12 + Test Coverage Audit

**What I built:** Three chunking strategies (fixed-size, semantic, structural) wired into the real processing pipeline, a comparison script that found a real bug, and a full test coverage audit that uncovered a coverage-measurement bug of its own plus several genuine testing gaps.

**What I learned:**

This phase was mainly about finally making the chunking system real and verifying whether all the work done so far was actually being tested properly.

The problem we were solving was that although the `chunks` table had existed since Week 5-6, nothing ever populated it. Every document had a `chunk_count` of zero. Chunking is important because documents are usually too large to send to an LLM at once, and embeddings work much better on smaller, focused pieces of content. It also makes citations more precise since we can point to a specific chunk instead of an entire document.

Before building the chunkers, we extended the extraction layer by adding heading support. Word documents already contain real heading information through styles such as Title, Heading 1, and Heading 2, so we extracted that directly instead of trying to infer structure ourselves. Other formats such as PDF, Excel, and plain text were left unsupported because there was no reliable way to get the same information without much heavier processing.

We then built three different chunking strategies. Fixed-size chunking was the simplest approach and just sliced text into windows based on size limits. It does not understand words, sentences, or topics, so it can easily cut content in the middle of a sentence or even a word. Semantic chunking was more intelligent and grouped sentences together based on topic similarity using term-frequency vectors and cosine similarity. Structural chunking used document headings when available and otherwise fell back to paragraph boundaries. This became the default strategy because it generally preserves the original document structure best.

The chunking system was then integrated into the real processing pipeline. After extraction completes, documents are automatically chunked and real `Chunk` rows are stored in the database. The chunk table is now actually being used, and `chunk_count` reflects the real number of chunks created for each document.

To compare the strategies, we ran all three against a real 34KB document. The results clearly showed why fixed-size chunking is considered a weak baseline. Most of its chunks started or ended in awkward places because it had no understanding of structure. Semantic and structural chunking produced much cleaner results and preserved context much better.

The comparison script also exposed a genuine bug. Structural chunking was creating only a single chunk for the entire document. After debugging, we found that the document used Windows-style line endings while the paragraph splitter only recognized Unix-style line endings. Since no paragraph breaks were detected, the entire document became one giant chunk. Normalizing line endings inside the structural chunker fixed the problem.

The second part of this work came from auditing test coverage. One of the roadmap goals was achieving complete coverage on all non-trivial functions, but we had never actually measured it. After adding coverage reporting, the initial result was only 84%, and one of the most heavily-tested files showed surprisingly low coverage.

The interesting discovery was that the coverage tool itself was partially responsible. SQLAlchemy's async implementation uses greenlets internally, and the coverage tracer was not following execution correctly across those greenlet switches. This caused large portions of code to appear untested even though they were executing successfully during tests. After enabling greenlet support in the coverage configuration, the numbers immediately became much more accurate.

Once the reporting issue was fixed, we started addressing the real gaps that remained. We added tests for the global exception handler, generic processing failures, endpoint consistency checks, PDF table extraction, document metadata extraction, Word title metadata, invalid text file handling, and several chunking edge cases. Many of these features had been manually verified before, but they had never been formally covered by automated tests.

One useful thing that came out of this exercise was finding dead code. While writing a test for a defensive check inside the semantic chunker's cosine similarity logic, I realized the condition could never actually occur. The math made it impossible for that branch to be reached, so instead of creating a meaningless test, we removed the code entirely. That was a good reminder that coverage work is not only about increasing percentages — it can also expose unnecessary code that should not exist in the first place.

By the end of the audit, coverage increased significantly, and the remaining uncovered code was limited to the PDF garbled-text recovery paths. Those branches were intentionally left as-is because the original issue only appeared on real invoices and could not be reproduced reliably with synthetic test files. Instead of forcing a brittle test, that functionality continues to be validated using the real documents that originally exposed the bug.

---

## 2026-09-03 — Phase 1, Week 13-14: Embedding Models

**What I built:** A real embedding pipeline using `BAAI/bge-large-en-v1.5` via `sentence-transformers`, wired into the processing pipeline so chunks finally get real vectors instead of `NULL`. Closed a roadmap gap (`section_heading`) and made two genuinely surprising discoveries by actually measuring things instead of assuming.

**What I learned:**

We first sorted out the PyTorch install. `sentence-transformers` pulls in PyTorch along with it, and by default PyTorch grabs the CUDA build which is a few GB. We don't have a GPU and at this scale we don't really need one, so we configured `[tool.uv.sources]` and `[[tool.uv.index]]` in `pyproject.toml` to pull the CPU-only wheel instead.

Now, we also created `src/docmind/embedding/embedder.py` which is the file that actually turns text into vectors. A few things going on here. First, loading the model is expensive — around 1.3GB of weights — so we cached it by name using `@lru_cache`. This means the model loads once per model name and not once for every `Embedder` object we create. Second, `embed_batch()` passes `normalize_embeddings=True`, which just shrinks every vector down to unit length. `bge-large` is trained and evaluated this way, and it also means cosine similarity becomes a plain dot product, which lines up with the `vector_cosine_ops` we set on the HNSW index back in Week 5-6. Third, the model name is a constructor argument instead of being hardcoded. We went and verified that `BAAI/bge-large-en-v1.5` really does output 1024 dimensions, which matches the `Vector(1024)` column we set up in Week 5-6 — so past us guessed right there. Tests use a much smaller model (`all-MiniLM-L6-v2`, 384 dims, ~90MB) so the test suite isn't downloading 1.3GB every time it runs.

We also closed a real gap in the roadmap. The roadmap says we should be storing "document ID, chunk position, page number, section heading" — and that last field just never got built. So we added `TextChunk.section_heading`, which gets filled in during structural chunking whenever an actual Word heading starts that chunk's section. That goes into a new `Chunk.section_heading` column in the DB (migration `523a2792a5ca`) and then gets exposed through `ChunkResponse`.

Then we wired all of this into the real pipeline. `process_document` now embeds every chunk in one single batch call instead of looping through them one at a time, and saves the vector alongside `section_heading`. We verified this running live in the container — 17 real chunks, and every single one came back with a genuine 1024-dim embedding.

Now, we also found two things by actually measuring stuff, and both were kind of surprising.

The first one is that batching barely helps with the model we're actually using. We built `scripts/measure_embedding_batching.py` fully expecting it to confirm the roadmap's "never embed one at a time" rule. But with `bge-large-en-v1.5` we got a 0.97x-0.98x speedup, which is basically nothing, and that held at both 17 chunks and 200 chunks. Then we ran the same test with the smaller `all-MiniLM-L6-v2` and got a real 1.4-6x speedup. So what we learned is that batching helps by spreading the fixed per-call overhead across a bunch of items. With a small fast model that overhead is a big chunk of the total time, so removing it matters a lot. But with `bge-large`, each call is already ~800ms of pure compute, so there's barely any overhead left for batching to remove on CPU. Our guess is this would flip on a GPU, which becomes relevant again in Phase 4, but we couldn't test it since there's no GPU here — so we wrote it down as a hypothesis and not a measured claim. The pipeline still batches, because batching is never worse and it's the right thing for smaller models or a future GPU deployment. The script just now honestly shows what actually happens with the model this app runs.

The second one is that the machine ran out of memory, and it looked like three different unrelated bugs before we found the real cause. What happened is we ran the full test suite while the Docker container was up (Langfuse alone is 8 services), and we first got a "paging file is too small" `OSError`. Then on the retry we got a raw Windows access violation crash inside `transformers`' native model-loading code. We initially chased this as a library bug and tried disabling threaded loading with `HF_DEACTIVATE_ASYNC_LOAD`, which did nothing. The real cause turned out to be that there was only 0.62GB of free RAM out of 15.24GB total. And stopping the containers didn't fully give it back either — Docker's WSL2 VM holds onto its memory balloon until it restarts — so we had to run `wsl --shutdown`, which got us back to about 5GB free. Since Langfuse isn't even wired into the app yet (that's Phase 3) and its 6 containers, including ClickHouse and MinIO, are the heaviest part of the whole stack, we made it opt-in through a Docker Compose profile instead of always-on. So now a plain `docker compose up` only starts `app`, `db`, and `redis`, and you run `docker compose --profile langfuse up -d` when you actually need the observability stack.

---

## 2026-09-03 — Phase 1, Week 15-16: Hybrid Retrieval

**What I built:** Dense + sparse (hand-rolled BM25) retrieval, fused with Reciprocal Rank Fusion and reranked with a cross-encoder, exposed through a new `/api/v1/search` endpoint. Evaluated all four configurations on 20 real questions and found a genuine surprise worth investigating instead of ignoring.

**What I learned:**

So we added full-text search to the schema. `Chunk.text_search` is a generated `tsvector` column, which means Postgres derives and stores it automatically on every insert and update rather than computing it at query time. This is the sparse/lexical half of hybrid search, sitting alongside the vector index we've had since Week 5-6.

Now, we created `src/docmind/retrieval/` with five modules in it.

`dense.py` is the straightforward one — it embeds the query and asks pgvector for the nearest neighbors by cosine distance.

`sparse.py` is real BM25, hand-rolled, and we deliberately did not use Postgres's own `ts_rank`. The idea is that the index is good at quickly finding candidates — any chunk containing any of the query terms — but the actual scoring, meaning term frequency with saturation, IDF, and document-length normalization, is done in Python. This week's reading was the Okapi BM25 paper, and implementing it yourself is what "understand the algorithm" actually means. Leaning on a library or on Postgres's own ranking formula would skip the part where you learn it.

`fusion.py` does Reciprocal Rank Fusion, which combines the dense and sparse rankings by position rather than by raw score. That's the important bit — a cosine similarity and a BM25 score aren't on comparable scales, so you can't just add them together.

`reranker.py` wraps a cross-encoder, and this is fundamentally different from the embedding model. A cross-encoder feeds the query and the chunk into the model together, which makes it much more accurate, but it means one forward pass per pair — way too slow to run across a whole corpus. So it only reranks the small candidate set that hybrid search has already narrowed down.

`hybrid.py` ties all of it together into the 4 configurations the roadmap's evaluation table names.

We also added the `/api/v1/search` endpoint. This is the first point where DocMind actually answers a question about its documents instead of just ingesting them, and we verified it live against the real containerized pipeline.

Then we did the 20-question evaluation, and this is where we got an honest surprise. 10 exact-lookup questions and 10 semantic ones, run against a real ingested document, measuring hit@5.

| Method | Exact | Semantic | Overall |
|--------|-------|----------|---------|
| Dense only | 90% | 90% | 90% |
| Sparse only (BM25) | 90% | 80% | 85% |
| Hybrid, no rerank | 90% | 100% | 95% |
| Hybrid + rerank | 100% | 90% | 95% |

Hybrid did beat either method on its own, which is what was predicted. But dense-only scoring 90% on the exact questions flatly contradicts the roadmap's claim that dense is bad at exact lookups, and that felt worth digging into rather than just shrugging at.

What we found is that our "exact" questions were still natural-language questions loaded with semantic context — something like "What is the exact embedding model specified for production use?" — which the embedding model can partly answer from meaning alone, without ever needing the identifier. So we isolated a sharper version of the test: two chunks identical except for one digit sequence, queried by the bare identifier.

Dense retrieval does still rank the correct one higher — but by a margin of only 0.03, where genuinely different topics usually separate by 0.1 to 0.3 or more. That's the real finding. Dense retrieval isn't blind to exact identifiers, it's just fragile about them. A margin that thin would routinely lose to unrelated-but-more-similar-overall chunks once you're working with a real, larger corpus. We wrote that up honestly in the script instead of reshaping the questions until they matched the prediction.

---
