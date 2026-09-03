import pytest

from docmind.db.base import async_session_factory
from docmind.embedding.embedder import Embedder
from docmind.retrieval.hybrid import hybrid_search
from docmind.retrieval.reranker import Reranker
from tests.retrieval.helpers import delete_document, make_document_with_chunks

_EMBED_MODEL = "BAAI/bge-large-en-v1.5"
_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@pytest.mark.asyncio
async def test_hybrid_search_finds_exact_identifier_via_sparse_side() -> None:
    # This is the exact scenario the roadmap motivates hybrid search
    # with: an exact identifier a dense-only search could easily miss,
    # found here because sparse retrieval feeds into the same fused list.
    embedder = Embedder(_EMBED_MODEL)
    texts = [
        "Invoice reference PO-2024-88421 was processed successfully.",
        "The team celebrated a successful product launch this week.",
    ]
    vectors = embedder.embed_batch(texts)
    doc_id, chunk_ids = await make_document_with_chunks(texts, embeddings=vectors)

    try:
        async with async_session_factory() as db:
            results = await hybrid_search(
                db, "PO-2024-88421", embedder, document_id=doc_id, reranker=None
            )
        assert chunk_ids[0] in [r.chunk_id for r in results]
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_hybrid_search_with_reranker_respects_limit() -> None:
    embedder = Embedder(_EMBED_MODEL)
    texts = ["Alpha content here.", "Beta content there.", "Gamma content elsewhere."]
    vectors = embedder.embed_batch(texts)
    doc_id, chunk_ids = await make_document_with_chunks(texts, embeddings=vectors)

    try:
        reranker = Reranker(_RERANK_MODEL)
        async with async_session_factory() as db:
            results = await hybrid_search(
                db,
                "Alpha content",
                embedder,
                document_id=doc_id,
                reranker=reranker,
                limit=2,
            )
        assert len(results) <= 2
        assert all(r.chunk_id in chunk_ids for r in results)
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_hybrid_search_no_reranker_returns_rrf_fused_results() -> None:
    embedder = Embedder(_EMBED_MODEL)
    texts = ["Some searchable content about widgets."]
    vectors = embedder.embed_batch(texts)
    doc_id, chunk_ids = await make_document_with_chunks(texts, embeddings=vectors)

    try:
        async with async_session_factory() as db:
            results = await hybrid_search(
                db, "widgets", embedder, document_id=doc_id, reranker=None
            )
        assert [r.chunk_id for r in results] == chunk_ids
    finally:
        await delete_document(doc_id)
