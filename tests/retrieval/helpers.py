"""Shared helpers for retrieval tests — real DB rows, not mocks.

Retrieval tests share the same dev Postgres database as every other
test in this suite (no isolated test schema), and BM25 scoring in
sparse.py depends on corpus-wide statistics (total chunk count, how
many chunks contain each term) that these helpers can't fully control.
So sparse/dense tests assert relative ordering and membership within
their own inserted chunks, never exact scores or exact result-list
positions — see test_sparse.py and test_dense.py for how that plays out.
"""

import uuid

from docmind.db.base import async_session_factory
from docmind.db.models import Chunk, Document, DocumentStatus


async def make_document_with_chunks(
    chunk_texts: list[str],
    embeddings: list[list[float]] | None = None,
    token_counts: list[int] | None = None,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Insert a Document + Chunks directly, bypassing extraction/chunking —
    retrieval tests need exact control over chunk text (and optionally
    embeddings), not realistic extraction behavior."""
    async with async_session_factory() as db:
        document = Document(
            filename="retrieval_test.txt",
            content_type="text/plain",
            status=DocumentStatus.DONE,
            chunk_count=len(chunk_texts),
        )
        db.add(document)
        await db.flush()

        chunk_ids: list[uuid.UUID] = []
        for i, chunk_text in enumerate(chunk_texts):
            chunk = Chunk(
                document_id=document.id,
                chunk_index=i,
                text=chunk_text,
                token_count=(
                    token_counts[i] if token_counts else len(chunk_text.split())
                ),
                embedding=embeddings[i] if embeddings else None,
            )
            db.add(chunk)
            await db.flush()
            chunk_ids.append(chunk.id)

        await db.commit()
        return document.id, chunk_ids


async def delete_document(document_id: uuid.UUID) -> None:
    async with async_session_factory() as db:
        document = await db.get(Document, document_id)
        if document is not None:
            await db.delete(document)
            await db.commit()
