# Confusion Log

> "Treat confusion as information. Never move on from something broken without understanding why."

Record everything that didn't work as expected. Investigate. Write the resolution. Review monthly.

---

## Template

### [Date] — [Topic]
**What I expected:**
**What actually happened:**
**Why:**
**Resolution:**

---

### 2026-06-09 — Docker WSL 2 Backend Missing
**What I expected:** Docker Desktop to launch successfully after installation.
**What actually happened:** Docker crashed with: `The Windows Subsystem for Linux is not installed.`
**Why:** Windows requires WSL (Windows Subsystem for Linux) to run Linux containers natively. We installed Docker, but the host OS lacked the underlying Linux kernel interface.
**Resolution:** Open an **Administrator** PowerShell, run `wsl.exe --install`, and restart the machine.

<!-- Start logging above -->

### 2026-08-19 — Langfuse ClickHouse Crash Loop
**What I expected:** `langfuse-web` and `langfuse-worker` to start cleanly once ClickHouse, MinIO, Postgres, and Redis were all healthy — the official Langfuse compose reference lists `CLICKHOUSE_CLUSTER_ENABLED` alongside a bunch of other optional-looking feature flags (SMTP, Azure blob, OCI storage, LLM connection whitelisting) that we didn't set explicitly.
**What actually happened:** `langfuse-web` crash-looped on startup with `error: failed to open database: ... There is no Zookeeper configuration in server config` while trying to run `CREATE TABLE schema_migrations ON CLUSTER default (...) Engine=ReplicatedMergeTree`.
**Why:** The official reference file sets `CLICKHOUSE_CLUSTER_ENABLED: ${CLICKHOUSE_CLUSTER_ENABLED:-false}` explicitly. We left it unset assuming it was harmless. Without that explicit `false`, the Langfuse image's own internal default is clustered mode — which uses `ReplicatedMergeTree` table engines that require a Zookeeper ensemble for coordination. We never provisioned Zookeeper, so ClickHouse rejected the migration outright. Not every env var in a reference compose file is truly optional just because it has a `${VAR:-default}` fallback syntax — the fallback only applies if *we* omit the variable from our own file too; when we drop the line entirely, the image falls back to its own internal default, which can differ from the reference's default.
**Resolution:** Added `CLICKHOUSE_CLUSTER_ENABLED: "false"` explicitly to the `langfuse-worker`/`langfuse-web` shared environment block in `docker-compose.yml`, then recreated both containers. ClickHouse came up standalone and the migrations applied successfully.

### 2026-08-31 — PDF Text Scrambled by Overlapping Columns (TallyPrime invoices)
**What I expected:** Our PDF extractor already had a fallback — if `pdfplumber` returned empty text for a page, retry with `pymupdf`. That felt like it covered the failure modes: either extraction works, or it visibly doesn't (empty output).
**What actually happened:** Testing against 5 real invoices, 2 of them (both exported from TallyPrime) came back with non-empty but completely scrambled text — `"P Po ri s v t a O te ff ic L e im"` instead of `"Post Office"`. The fallback never triggered because the text wasn't empty, just wrong.
**Why:** These specific invoices lay out two blocks of text (address columns) at overlapping y-coordinates on the page. `pdfplumber` sorts glyphs primarily by vertical position when reconstructing lines, so when two blocks share a y-range, characters from both interleave into one garbled line. This is a real, known failure mode of geometry-based PDF text reconstruction, not a bug in `pdfplumber` itself — it's genuinely ambiguous from glyph positions alone which characters belong to which block. "Did extraction return text?" turned out not to be a sufficient success check — extraction can succeed mechanically while still being wrong.
**Resolution:** Measured a heuristic across the real files — the fraction of extracted whitespace-separated tokens that are ≤2 characters long. The 2 garbled invoices scored 0.39-0.40; the 3 clean ones scored 0.14-0.22, a clean separation. Added `_looks_garbled()` in `pdf.py` using a 0.30 threshold (with a 20-token minimum, so short pages can't false-positive), and widened the existing pymupdf-fallback trigger to fire on garbled text, not just empty text. Verified against both real problem invoices — both now extract clean, correctly-ordered text, flagged with a warning noting the recovery. Could not fully reproduce the exact scrambling statistics in a synthetic test PDF (attempts scored 0.14-0.24, never crossing 0.30) — the heuristic is validated against real files and a direct unit test of the function using the actual garbled text, not an automated end-to-end repro.

### 2026-08-31 — Extracted Tables Silently Discarded
**What I expected:** Since `extraction.tables` was part of the `ExtractionResult` returned by every extractor, and the roadmap's own goal for this week was "an extraction layer that returns a structured representation," I assumed the processing pipeline was actually storing all of it.
**What actually happened:** Yash tested a real invoice through the API and got back a `content` field with the invoice's line-item table flattened into prose, columns visibly out of order (quantity landing on its own line, after price and total). No structured table data appeared anywhere in the response.
**Why:** `process_document` in `documents.py` only ever wrote `extraction.text` and `extraction.metadata` onto the `Document` row — `extraction.tables` was computed correctly by the extractor (verified independently: `pdfplumber`'s `extract_tables()` had the right column order) but never assigned to anything, so it was discarded the moment the background task's local variables went out of scope. A correct extraction result does not guarantee a correct persistence step — each field has to actually be wired to storage on purpose.
**Resolution:** Added `document.metadata_["tables"]` = the list of extracted tables (as plain JSON via `.model_dump()`) in `process_document`, alongside the existing `text`/`warnings`/`metadata` fields. Re-tested against the real invoice — all 3 of its tables, including a table split across a page boundary, now appear in the API response with column alignment intact.

### 2026-08-31 — Structural Chunking Produced One Giant Chunk for a 34KB File
**What I expected:** Running `scripts/compare_chunking.py` against `Docs/DocMind.txt` (34KB, dozens of paragraphs) with `target_tokens=512`, I expected structural chunking to produce roughly as many chunks as fixed-size and semantic did (19 and 41 respectively).
**What actually happened:** Structural chunking produced exactly **1 chunk**, 8504 tokens, for the entire file.
**Why:** `_paragraphs()` in `structural.py` split text on the literal string `"\n\n"`. `Docs/DocMind.txt` is a Windows-authored file, so its actual paragraph breaks are `"\r\n\r\n"`. The split found zero matches in the whole file, so the entire document came back as a single "paragraph." `semantic.py` was unaffected by the same file because its sentence-splitter regex (`(?<=[.!?])\s+`) matches any whitespace, CRLF included — only the literal-string split in the structural chunker was line-ending-sensitive. `text.py`'s extractor was working correctly the whole time (`bytes.decode("utf-8")` faithfully preserves whatever line endings the source file used — Python does not do universal-newline translation on `bytes.decode()`), so this was never an extraction bug, only a chunking-side assumption.
**Resolution:** Added `text.replace("\r\n", "\n").replace("\r", "\n")` inside `_paragraphs()` specifically — not in extraction, which should stay a byte-for-byte faithful copy of the source. Re-ran the script: structural chunking now produces 17 sensible chunks. Added a regression test using literal `"\r\n\r\n"` in a synthetic `ExtractionResult`.

### 2026-08-31 — Coverage Tool Silently Under-Reporting Async Route Coverage
**What I expected:** After adding `pytest-cov` to check Week 1-2's "100% test coverage" claim for the first time, I expected `documents.py` — the most heavily-tested file in the project, exercised by dozens of tests — to show high coverage.
**What actually happened:** `documents.py` showed **37%**, with `coverage` claiming the entire body of every route handler after its first `await db.execute(...)` call never executed — including code that tests were clearly exercising (uploads succeeded, content came back correct, chunks were queryable).
**Why:** SQLAlchemy's async engine bridges to its underlying sync DBAPI driver via **greenlet** switches — a real context-switch mechanism, not just an abstraction. `coverage.py` installs its tracer via `sys.settrace()`, which by default does not follow execution across a greenlet switch. So every line that ran *after* control passed through a greenlet boundary looked, to the tracer, like it never ran — even though it plainly had. This is a known, documented interaction (`coverage.py` has explicit support for it, added because of exactly this SQLAlchemy pattern), not a bug in either library — just a measurement tool that needs to be told about a non-standard execution model to trust its own numbers.
**Resolution:** Added `concurrency = ["greenlet", "thread"]` under `[tool.coverage.run]` in `pyproject.toml`. Re-ran: overall coverage jumped from 84% to 93% purely from the measurement becoming accurate, with `documents.py` alone going from 37% to 88% real coverage. Lesson worth keeping: an unexpectedly bad number is sometimes a bug in the thing measuring, not the thing being measured — verify the tool before trusting the result.
