"""Orchestrates dense + sparse retrieval, fused by RRF, optionally reranked.

This is the actual "hybrid search" the roadmap asks for — the other
modules (dense, sparse, fusion, reranker) are all building blocks this
one wires together into the 4 configurations
scripts/evaluate_retrieval.py compares:
  dense only        -> dense_search()
  sparse only       -> sparse_search()
  hybrid, no rerank -> hybrid_search(..., reranker=None)
  hybrid + rerank   -> hybrid_search(..., reranker=Reranker(...))
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from docmind.embedding.embedder import Embedder
from docmind.retrieval.dense import dense_search
from docmind.retrieval.fusion import reciprocal_rank_fusion
from docmind.retrieval.models import ScoredChunk
from docmind.retrieval.reranker import Reranker
from docmind.retrieval.sparse import sparse_search


async def hybrid_search(
    db: AsyncSession,
    query: str,
    embedder: Embedder,
    limit: int = 10,
    candidate_limit: int = 20,
    reranker: Reranker | None = None,
    document_id: uuid.UUID | None = None,
) -> list[ScoredChunk]:
    """Dense + sparse retrieval, fused by RRF, optionally cross-encoder reranked."""
    query_vector = embedder.embed_batch([query])[0]

    dense_results = await dense_search(
        db, query_vector, limit=candidate_limit, document_id=document_id
    )
    sparse_results = await sparse_search(
        db, query, limit=candidate_limit, document_id=document_id
    )

    fused = reciprocal_rank_fusion(
        [dense_results, sparse_results], limit=candidate_limit
    )

    if reranker is None:
        return fused[:limit]
    return reranker.rerank(query, fused, limit=limit)
