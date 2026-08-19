"""EXPLAIN ANALYZE script for DocMind's 5 most common query patterns.

This script:
1. Seeds the database with sample documents, chunks, and random embeddings
2. Runs EXPLAIN ANALYZE on each of the 5 core queries
3. Prints the query plan and writes it to scripts/explain_output.txt

Run with: uv run python scripts/explain_queries.py
"""

import asyncio
import random
import uuid

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.db.base import async_session_factory, engine
from docmind.db.models import Base, Chunk, Document, DocumentStatus

# Number of sample records to create
NUM_DOCUMENTS = 100
NUM_CHUNKS_PER_DOC = 10
EMBEDDING_DIM = 1024

output_lines = []


def log(msg: str = "") -> None:
    """Print to console and append to file output list."""
    print(msg)
    output_lines.append(msg)


async def seed_data(session: AsyncSession) -> list[uuid.UUID]:
    """Insert sample documents and chunks with random embeddings."""
    log("\n[Seed] Seeding database with sample data...")
    log(
        f"   Creating {NUM_DOCUMENTS} documents with "
        f"{NUM_CHUNKS_PER_DOC} chunks each"
    )
    log(f"   Total chunks: {NUM_DOCUMENTS * NUM_CHUNKS_PER_DOC}")

    statuses = list(DocumentStatus)
    doc_ids: list[uuid.UUID] = []

    for i in range(NUM_DOCUMENTS):
        doc = Document(
            filename=f"document_{i:03d}.pdf",
            content_type="application/pdf",
            status=random.choice(statuses),
            metadata_={
                "page_count": random.randint(1, 500),
                "author": random.choice(["Yash", "Alice", "Bob", "Charlie"]),
                "language": random.choice(["en", "hi", "fr", "de"]),
                "file_size_kb": random.randint(100, 50000),
            },
            chunk_count=NUM_CHUNKS_PER_DOC,
        )
        session.add(doc)

        for j in range(NUM_CHUNKS_PER_DOC):
            chunk = Chunk(
                chunk_index=j,
                text=f"This is chunk {j} of document {i}. "
                     f"It contains sample text for testing purposes.",
                embedding=np.random.randn(EMBEDDING_DIM).tolist(),
                token_count=random.randint(100, 512),
                page_numbers=[j + 1, j + 2],
            )
            doc.chunks.append(chunk)
        
        await session.flush()
        doc_ids.append(doc.id)

    await session.commit()
    total_chunks = NUM_DOCUMENTS * NUM_CHUNKS_PER_DOC
    log(
        f"   [Success] Seeded {NUM_DOCUMENTS} documents "
        f"and {total_chunks} chunks\n"
    )
    return doc_ids


async def run_explain(session: AsyncSession, label: str, query: str) -> None:
    """Run EXPLAIN ANALYZE on a query and print the plan."""
    log(f"{'=' * 70}")
    log(f"Plan for: {label}")
    log(f"{'=' * 70}")
    log(f"SQL: {query.strip()}\n")

    result = await session.execute(text(f"EXPLAIN ANALYZE {query}"))
    rows = result.fetchall()

    for row in rows:
        log(f"  {row[0]}")

    log()


async def main() -> None:
    """Seed data and run EXPLAIN ANALYZE on 5 query patterns."""

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Clean up any existing test data
        await session.execute(text("DELETE FROM chunks"))
        await session.execute(text("DELETE FROM documents"))
        await session.commit()

        # Seed fresh data
        doc_ids = await seed_data(session)

        # Pick a random document ID for targeted queries
        sample_id = doc_ids[0]

        # Generate a random query vector for similarity search
        query_vector = np.random.randn(EMBEDDING_DIM).tolist()
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        # Disable sequential scans so PostgreSQL is forced to use our indexes
        # even with only 100 documents / 1000 chunks. This simulates behavior
        # on production-sized datasets.
        await session.execute(text("SET enable_seqscan = off"))

        log("\n[Analyze] Running EXPLAIN ANALYZE on 5 core query patterns...\n")

        # ─────────────────────────────────────────────────────
        # Query 1: Find document by ID (Primary Key Index Scan)
        # ─────────────────────────────────────────────────────
        await run_explain(
            session,
            "1 — Find Document by ID (should use Primary Key Index Scan)",
            f"SELECT * FROM documents WHERE id = '{sample_id}'",
        )

        # ─────────────────────────────────────────────────────
        # Query 2: Get all chunks for a document, ordered
        #          (should use composite B-tree index)
        # ─────────────────────────────────────────────────────
        await run_explain(
            session,
            "2 — Get Chunks for Document, Ordered (should use composite index)",
            f"SELECT * FROM chunks WHERE "
            f"document_id = '{sample_id}' ORDER BY chunk_index",
        )

        # ─────────────────────────────────────────────────────
        # Query 3: Filter documents by status
        #          (should use B-tree index on status)
        # ─────────────────────────────────────────────────────
        await run_explain(
            session,
            "3 — Filter Documents by Status (should use status index)",
            "SELECT * FROM documents WHERE status = 'DONE'",
        )

        # ─────────────────────────────────────────────────────
        # Query 4: Search JSONB metadata
        #          (should use GIN index with @> operator)
        # ─────────────────────────────────────────────────────
        await run_explain(
            session,
            "4 — Search JSONB Metadata (should use GIN index)",
            """SELECT * FROM documents WHERE metadata_ @> '{"language": "en"}'""",
        )

        # ─────────────────────────────────────────────────────
        # Query 5: Find similar chunks by vector (cosine distance)
        #          (should use HNSW index)
        # ─────────────────────────────────────────────────────
        await run_explain(
            session,
            "5 — Vector Similarity Search (should use HNSW index)",
            f"SELECT id, text, embedding <=> '{vector_str}' AS distance "
            f"FROM chunks ORDER BY embedding <=> '{vector_str}' LIMIT 5",
        )

        # Clean up test data
        log("[Clean] Cleaning up test data...")
        await session.execute(text("DELETE FROM chunks"))
        await session.execute(text("DELETE FROM documents"))
        await session.commit()
        log("[Success] Done!\n")

    await engine.dispose()

    # Write output to scripts/explain_output.txt in UTF-8
    with open("scripts/explain_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))


if __name__ == "__main__":
    asyncio.run(main())
