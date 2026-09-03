"""Evaluate dense-only, sparse-only, hybrid, and hybrid+rerank retrieval
on 20 hand-written questions against a real document — the roadmap's
Week 15-16 evaluation exercise.

Every question was written by reading the actual chunks this script
ingests (Docs/DocMind.txt, chunked structurally into 17 pieces — see
the chunk dump used to write questions), each with a known correct
chunk index. Ten questions are exact/specific lookups (a model name,
an API path, a cost figure — the "PO-2024-1234" case from the
roadmap), and ten are semantic/conceptual (paraphrased, no meaningful
keyword overlap with their answer chunk) — this split is what lets the
comparison actually show dense vs. sparse's opposite failure modes,
not just "one number is bigger."

Metric: hit@5 — does a chunk with the expected index appear in the
top 5 results? Simple, and enough to see most of the roadmap's
predicted pattern — but not all of it: dense-only scored 90% on
"exact" questions here, not "bad" as predicted. Why: even the "exact"
questions were natural-language questions with real semantic content
around the fact being asked, which bge-large can partly answer from
meaning alone. The addendum at the end isolates the sharper case the
roadmap's "PO-2024-1234" example is really about — two chunks
identical except for one digit sequence, queried by that identifier
alone — which does show a real (if surprisingly small) dense
similarity margin between the right and wrong chunk. Reported
honestly rather than reshaping the 20 questions until the numbers
matched the prediction.

Run with: uv run python scripts/evaluate_retrieval.py
(ingests Docs/DocMind.txt fresh each run and deletes it when done)
"""

import asyncio
import sys
from pathlib import Path

# This script lives outside the installed package (there's no
# [build-system] in pyproject.toml, so `docmind` is never actually
# installed — only pytest's `pythonpath = ["src"]` makes imports work
# during tests). Standalone scripts need the same path added manually.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docmind.chunking.strategy import chunk_document  # noqa: E402
from docmind.core.config import settings  # noqa: E402
from docmind.db.base import async_session_factory  # noqa: E402
from docmind.db.models import Chunk, Document, DocumentStatus  # noqa: E402
from docmind.embedding.embedder import Embedder  # noqa: E402
from docmind.extraction.router import extract  # noqa: E402
from docmind.retrieval.dense import dense_search  # noqa: E402
from docmind.retrieval.hybrid import hybrid_search  # noqa: E402
from docmind.retrieval.reranker import Reranker  # noqa: E402
from docmind.retrieval.sparse import sparse_search  # noqa: E402

DOCUMENT_PATH = Path("Docs/DocMind.txt")
TOP_K = 5

# (question, expected chunk_index(es), category)
QUESTIONS: list[tuple[str, list[int], str]] = [
    # --- Exact / specific lookups (favor sparse) ---
    ("What is the exact embedding model specified for production use?", [1], "exact"),
    ("How many requests per day does the free Gemini API tier allow?", [1], "exact"),
    (
        "What is the estimated Azure AKS cost after the free credit runs out?",
        [12],
        "exact",
    ),
    ("What are the three tools given to the from-scratch ReAct agent?", [7], "exact"),
    ("What is the exact API endpoint for checking a document's status?", [3], "exact"),
    (
        "Which five specialist roles make up the multi-agent architecture?",
        [9],
        "exact",
    ),
    (
        "How long is the Deep Work 1 block in the daily execution structure?",
        [14],
        "exact",
    ),
    (
        "What is the name of the foundational reasoning-and-acting paper for agents?",
        [7],
        "exact",
    ),
    (
        "What accuracy did the existing Azure Document Intelligence work achieve?",
        [16],
        "exact",
    ),
    (
        "What does the roadmap say certificates prove once you already have AI-102?",
        [15],
        "exact",
    ),
    # --- Semantic / conceptual (favor dense) ---
    (
        "Why is it okay to start building before fully understanding something?",
        [0],
        "semantic",
    ),
    (
        "What's the right way to react when code doesn't behave the way I expected?",
        [14],
        "semantic",
    ),
    (
        "How can I tell if I'm actually making progress or just staying busy?",
        [15],
        "semantic",
    ),
    (
        "What kind of skills will still matter years from now in AI engineering?",
        [16],
        "semantic",
    ),
    (
        "How should I compare ways of splitting a document before it goes to a model?",
        [5, 6],
        "semantic",
    ),
    (
        "What should an agent do if it can't make progress after many steps?",
        [8],
        "semantic",
    ),
    (
        "Why is a hand-crafted set of test questions valuable for checking retrieval?",
        [10],
        "semantic",
    ),
    (
        "What's a trap where relying too heavily on a framework backfires later?",
        [15],
        "semantic",
    ),
    (
        "How should someone spend their weekends to keep growing as an engineer?",
        [14],
        "semantic",
    ),
    (
        "What is my current biggest professional strength going into this roadmap?",
        [16],
        "semantic",
    ),
]

output_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    output_lines.append(msg)


async def ingest_document() -> tuple[object, dict[int, object]]:
    """Extract, chunk, and embed Docs/DocMind.txt; return (document_id,
    {chunk_index: chunk_id})."""
    data = DOCUMENT_PATH.read_bytes()
    extraction = extract(DOCUMENT_PATH.name, data)
    chunks = chunk_document(extraction, strategy=settings.chunking_strategy)

    embedder = Embedder(settings.embedding_model)
    vectors = embedder.embed_batch([c.text for c in chunks])

    async with async_session_factory() as db:
        document = Document(
            filename=DOCUMENT_PATH.name,
            content_type="text/plain",
            status=DocumentStatus.DONE,
            content=extraction.text,
            chunk_count=len(chunks),
        )
        db.add(document)
        await db.flush()

        index_to_id = {}
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            row = Chunk(
                document_id=document.id,
                chunk_index=i,
                text=chunk.text,
                embedding=vector,
                token_count=chunk.token_count,
                page_numbers=chunk.page_numbers or None,
                section_heading=chunk.section_heading,
            )
            db.add(row)
            await db.flush()
            index_to_id[i] = row.id

        await db.commit()
        return document.id, index_to_id


async def illustrate_dense_fragility(embedder: Embedder) -> None:
    """The 20-question set above showed dense-only scoring 90% on "exact"
    questions — not the "bad at exact" the roadmap predicts. Why: those
    questions were still natural-language questions with rich semantic
    content around the exact fact (e.g. "What is the exact embedding
    model specified for production use?"), which dense retrieval can
    partly answer from meaning alone. This isolates the sharper case
    the roadmap's own "PO-2024-1234" example is really about: two
    chunks identical except for one identifier, queried by that exact
    identifier alone.
    """
    chunk_a = (
        "Invoice reference PO-2024-88421 was processed successfully "
        "by the finance team."
    )
    chunk_b = (
        "Invoice reference PO-2024-99999 was processed successfully "
        "by the finance team."
    )
    query = "PO-2024-88421"

    vec_a, vec_b, vec_q = embedder.embed_batch([chunk_a, chunk_b, query])
    sim_a = sum(x * y for x, y in zip(vec_q, vec_a, strict=True))
    sim_b = sum(x * y for x, y in zip(vec_q, vec_b, strict=True))

    log(f"{'=' * 70}")
    log("Addendum: dense retrieval's real weak spot")
    log(f"{'=' * 70}")
    log("Two chunks, identical except one digit sequence; query = the exact ID.")
    log(f"  similarity to the CORRECT chunk:   {sim_a:.4f}")
    log(f"  similarity to the WRONG chunk:     {sim_b:.4f}")
    log(f"  margin: {sim_a - sim_b:.4f} (compare to ~0.1-0.3+ for genuinely")
    log("  different topics — this margin is real but fragile: in a large")
    log("  corpus, many chunks more semantically similar overall (but")
    log("  lacking this exact ID) could easily outscore the correct one.")
    log()


async def cleanup(document_id: object) -> None:
    async with async_session_factory() as db:
        document = await db.get(Document, document_id)
        if document is not None:
            await db.delete(document)
            await db.commit()


async def evaluate_method(
    name: str,
    run_query: object,
    index_to_id: dict[int, object],
) -> dict[str, float]:
    hits = {"exact": 0, "semantic": 0}
    totals = {"exact": 0, "semantic": 0}

    for question, expected_indices, category in QUESTIONS:
        results = await run_query(question)  # type: ignore[operator]
        result_ids = {r.chunk_id for r in results[:TOP_K]}
        expected_ids = {index_to_id[i] for i in expected_indices}

        totals[category] += 1
        if result_ids & expected_ids:
            hits[category] += 1

    log(f"{'=' * 70}")
    log(f"{name}")
    log(f"{'=' * 70}")
    rates = {}
    for category in ("exact", "semantic"):
        rate = hits[category] / totals[category] if totals[category] else 0.0
        rates[category] = rate
        h, t = hits[category], totals[category]
        log(f"  {category:9s} hit@{TOP_K}: {h}/{t} ({rate:.0%})")
    total_hits, total_all = sum(hits.values()), sum(totals.values())
    overall = total_hits / total_all
    rates["overall"] = overall
    log(f"  {'overall':9s} hit@{TOP_K}: {total_hits}/{total_all} ({overall:.0%})")
    log()
    return rates


async def main() -> None:
    log(f"\nIngesting {DOCUMENT_PATH} ...")
    document_id, index_to_id = await ingest_document()
    log(
        f"Ingested {len(index_to_id)} chunks. Running {len(QUESTIONS)} questions "
        f"(10 exact, 10 semantic) at hit@{TOP_K}.\n"
    )

    embedder = Embedder(settings.embedding_model)
    reranker = Reranker(settings.reranker_model)

    try:

        async def dense_only(q: str) -> list:  # type: ignore[type-arg]
            async with async_session_factory() as db:
                vector = embedder.embed_batch([q])[0]
                return await dense_search(
                    db, vector, limit=TOP_K, document_id=document_id
                )

        async def sparse_only(q: str) -> list:  # type: ignore[type-arg]
            async with async_session_factory() as db:
                return await sparse_search(db, q, limit=TOP_K, document_id=document_id)

        async def hybrid_no_rerank(q: str) -> list:  # type: ignore[type-arg]
            async with async_session_factory() as db:
                return await hybrid_search(
                    db, q, embedder, limit=TOP_K, reranker=None, document_id=document_id
                )

        async def hybrid_reranked(q: str) -> list:  # type: ignore[type-arg]
            async with async_session_factory() as db:
                return await hybrid_search(
                    db,
                    q,
                    embedder,
                    limit=TOP_K,
                    reranker=reranker,
                    document_id=document_id,
                )

        results = {}
        results["1 - Dense only"] = await evaluate_method(
            "1 - Dense only", dense_only, index_to_id
        )
        results["2 - Sparse only (BM25)"] = await evaluate_method(
            "2 - Sparse only (BM25)", sparse_only, index_to_id
        )
        results["3 - Hybrid, no rerank"] = await evaluate_method(
            "3 - Hybrid, no rerank", hybrid_no_rerank, index_to_id
        )
        results["4 - Hybrid + rerank"] = await evaluate_method(
            "4 - Hybrid + rerank", hybrid_reranked, index_to_id
        )

        log(f"{'=' * 70}")
        log("Summary")
        log(f"{'=' * 70}")
        log(f"  {'Method':25s} {'exact':>8s} {'semantic':>10s} {'overall':>9s}")
        for name, rates in results.items():
            log(
                f"  {name:25s} {rates['exact']:>7.0%} {rates['semantic']:>9.0%} "
                f"{rates['overall']:>8.0%}"
            )
        log()

        await illustrate_dense_fragility(embedder)
    finally:
        await cleanup(document_id)
        log("\nCleaned up ingested test document.")

    with open("scripts/retrieval_evaluation.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    asyncio.run(main())
