"""Dense retrieval — semantic similarity search via pgvector's HNSW index.

Embeds the query with the same model used for chunks (Week 13-14), then
asks Postgres for the chunks whose embedding vectors are closest by
cosine distance. This finds chunks that mean the same thing as the
query even when they don't share any words — the opposite failure mode
of sparse/lexical search (see sparse.py), and the reason hybrid search
combines both.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.db.models import Chunk
from docmind.retrieval.models import ScoredChunk


async def dense_search(
    db: AsyncSession,
    query_vector: list[float],
    limit: int = 20,
    document_id: uuid.UUID | None = None,
) -> list[ScoredChunk]:
    """Find chunks by embedding similarity to query_vector.

    score is cosine similarity (1 - cosine distance), so higher is
    better here — pgvector's <=> operator returns distance (lower is
    closer), which cosine_distance() wraps; we flip the sign for the
    score while still ordering by the raw distance expression.
    """
    distance = Chunk.embedding.cosine_distance(query_vector)
    stmt = select(Chunk, distance.label("distance")).where(
        Chunk.embedding.is_not(None)
    )
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    stmt = stmt.order_by(distance).limit(limit)

    result = await db.execute(stmt)
    return [
        ScoredChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            page_numbers=chunk.page_numbers,
            section_heading=chunk.section_heading,
            score=1.0 - distance_value,
        )
        for chunk, distance_value in result.all()
    ]
