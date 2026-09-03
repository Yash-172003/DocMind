"""Search endpoint — hybrid retrieval over ingested chunks.

The first endpoint where DocMind actually answers a question about
its documents, rather than just ingesting them (Phase 1's milestone
until now was "no question-answering yet"). Real answer generation
with citations is Week 17-18 — this endpoint returns ranked chunks,
not a synthesized answer.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.api.deps import get_db, verify_api_key
from docmind.core.config import settings
from docmind.embedding.embedder import Embedder
from docmind.retrieval.hybrid import hybrid_search
from docmind.retrieval.models import ScoredChunk
from docmind.retrieval.reranker import Reranker

logger = structlog.get_logger()

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=list[ScoredChunk])
async def search(
    q: str = Query(..., min_length=1, description="Search query text"),
    limit: int = Query(10, ge=1, le=50),
    document_id: uuid.UUID | None = Query(
        None, description="Restrict search to one document"
    ),
    rerank: bool = Query(
        True, description="Apply cross-encoder reranking (slower, more accurate)"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[ScoredChunk]:
    """Hybrid search: dense (embeddings) + sparse (BM25) fused by RRF."""
    embedder = Embedder(settings.embedding_model)
    reranker = Reranker(settings.reranker_model) if rerank else None

    results = await hybrid_search(
        db,
        q,
        embedder,
        limit=limit,
        reranker=reranker,
        document_id=document_id,
    )
    logger.info("search_executed", query=q, result_count=len(results), rerank=rerank)
    return results
