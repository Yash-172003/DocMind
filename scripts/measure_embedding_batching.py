"""Measure the real cost of embedding one chunk at a time vs. batching.

This script:
1. Extracts and structurally chunks Docs/DocMind.txt (a real ~34KB
   document already in this repo) to get a realistic set of chunk texts
2. Times one-at-a-time vs. one batched call, at this repo's real chunk
   count (17) and at a simulated multi-document scale (200)
3. Repeats the same comparison against a much smaller reference model
   (all-MiniLM-L6-v2) to explain *why* the result looks the way it does
4. Writes results to scripts/embedding_batch_comparison.txt

The actual finding here contradicts the roadmap's flat claim that
batching matters: with the real production model (BAAI/bge-large-en-
v1.5, 335M params), batching shows *no* measurable speedup on this
CPU — not at 17 chunks, not at 200. The smaller reference model
(all-MiniLM-L6-v2, 22M params) shows a real 5-6x speedup at the same
200-chunk scale.

Why: batching's benefit comes from amortizing *fixed* per-call
overhead (tokenization, Python dispatch, small-batch inefficiency)
across many items. For a small, fast model, that fixed overhead is a
large fraction of each call's total time, so batching removes a real
cost. For a large model like bge-large, a single inference call is
already ~800ms of pure matrix-multiplication work — compute-bound, not
overhead-bound — so there's very little fixed cost left for batching
to amortize on CPU. This is a CPU-specific result: GPU inference
parallelizes batched matrix operations far more effectively than CPU
BLAS does for a single large model, so this conclusion would likely
flip on GPU-backed infrastructure (relevant again in Phase 4). Not
tested here — no GPU available — so this is a documented hypothesis,
not a measured claim.

The pipeline still batches (see docmind.embedding.embedder) because
it's never worse, matches the roadmap's guidance for when it *does*
matter (smaller/faster models, or future GPU deployment), and keeps
one code path instead of two.

Run with: uv run python scripts/measure_embedding_batching.py
"""

import sys
import time
from pathlib import Path

# This script lives outside the installed package (there's no
# [build-system] in pyproject.toml, so `docmind` is never actually
# installed — only pytest's `pythonpath = ["src"]` makes imports work
# during tests). Standalone scripts need the same path added manually.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docmind.chunking.structural import chunk_structural  # noqa: E402
from docmind.core.config import settings  # noqa: E402
from docmind.embedding.embedder import Embedder, _load_model  # noqa: E402
from docmind.extraction.router import extract  # noqa: E402

DOCUMENT_PATH = Path("Docs/DocMind.txt")
REFERENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

output_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    output_lines.append(msg)


def compare_at_scale(embedder: Embedder, texts: list[str], label: str) -> float:
    """Returns the measured speedup factor."""
    log(f"{label} — {len(texts)} chunks, model={embedder.model_name}")

    t0 = time.perf_counter()
    for text in texts:
        embedder.embed_batch([text])
    one_at_a_time_seconds = time.perf_counter() - t0
    log(
        f"  One at a time:  {one_at_a_time_seconds:.2f}s total, "
        f"{one_at_a_time_seconds / len(texts) * 1000:.1f}ms/chunk"
    )

    t0 = time.perf_counter()
    embedder.embed_batch(texts, batch_size=settings.embedding_batch_size)
    batched_seconds = time.perf_counter() - t0
    log(
        f"  Batched:        {batched_seconds:.2f}s total, "
        f"{batched_seconds / len(texts) * 1000:.1f}ms/chunk"
    )

    speedup = one_at_a_time_seconds / batched_seconds if batched_seconds else 0.0
    log(f"  Speedup: {speedup:.2f}x\n")
    return speedup


def main() -> None:
    data = DOCUMENT_PATH.read_bytes()
    extraction = extract(DOCUMENT_PATH.name, data)
    chunks = chunk_structural(extraction, target_tokens=512)
    real_texts = [c.text for c in chunks]
    larger_texts = (real_texts * 12)[:200]

    log(f"\nDocument: {DOCUMENT_PATH} chunked into {len(real_texts)} pieces\n")

    log(f"{'=' * 70}")
    log(f"Production model: {settings.embedding_model}")
    log(f"{'=' * 70}")
    t0 = time.perf_counter()
    _load_model(settings.embedding_model)
    load_time = time.perf_counter() - t0
    log(f"Model load time: {load_time:.1f}s (one-time, excluded above)\n")

    prod_embedder = Embedder(settings.embedding_model)
    prod_small_speedup = compare_at_scale(
        prod_embedder, real_texts, "This repo's chunks"
    )
    prod_large_speedup = compare_at_scale(
        prod_embedder, larger_texts, "Multi-document scale"
    )

    log(f"{'=' * 70}")
    log(f"Reference model: {REFERENCE_MODEL} (for comparison only)")
    log(f"{'=' * 70}")
    t0 = time.perf_counter()
    _load_model(REFERENCE_MODEL)
    load_time = time.perf_counter() - t0
    log(f"Model load time: {load_time:.1f}s (one-time, excluded above)\n")

    ref_embedder = Embedder(REFERENCE_MODEL)
    ref_speedup = compare_at_scale(ref_embedder, larger_texts, "Multi-document scale")

    log(f"{'=' * 70}")
    log("Conclusion")
    log(f"{'=' * 70}")
    log(
        f"  {settings.embedding_model}: {prod_small_speedup:.2f}x at "
        f"{len(real_texts)} chunks, {prod_large_speedup:.2f}x at {len(larger_texts)}"
    )
    log(f"  {REFERENCE_MODEL}: {ref_speedup:.2f}x at {len(larger_texts)} chunks")
    log(
        "  The production model shows essentially no batching benefit on "
        "this CPU — each call is already compute-bound. The smaller "
        "reference model shows a real speedup because fixed per-call "
        "overhead is a much larger share of its (much shorter) runtime. "
        "See the module docstring for the full explanation."
    )

    with open("scripts/embedding_batch_comparison.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    main()
