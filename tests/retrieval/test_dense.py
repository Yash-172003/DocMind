"""Dense retrieval tests use the real BAAI/bge-large-en-v1.5 model, not a
smaller test model — the chunks.embedding column is Vector(1024), and
pgvector rejects a vector of the wrong dimension outright, so there's
no lighter-weight substitute here (unlike tests/embedding/, which only
exercises the Embedder class in isolation, never touching the DB).
"""

import pytest

from docmind.db.base import async_session_factory
from docmind.embedding.embedder import Embedder
from docmind.retrieval.dense import dense_search
from tests.retrieval.helpers import delete_document, make_document_with_chunks

_MODEL = "BAAI/bge-large-en-v1.5"


@pytest.mark.asyncio
async def test_dense_search_ranks_semantically_similar_chunk_first() -> None:
    embedder = Embedder(_MODEL)
    texts = [
        "The cat sat on a warm windowsill in the afternoon sun.",
        "Quarterly revenue grew by twelve percent across all regions.",
    ]
    vectors = embedder.embed_batch(texts)
    doc_id, chunk_ids = await make_document_with_chunks(texts, embeddings=vectors)

    try:
        query_vector = embedder.embed_batch(["A kitten napping by the window."])[0]
        async with async_session_factory() as db:
            results = await dense_search(db, query_vector, document_id=doc_id)

        assert [r.chunk_id for r in results] == chunk_ids  # cat chunk ranks first
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_dense_search_excludes_chunks_without_embeddings() -> None:
    doc_id, _ = await make_document_with_chunks(["Has no embedding at all."])
    try:
        embedder = Embedder(_MODEL)
        query_vector = embedder.embed_batch(["anything"])[0]
        async with async_session_factory() as db:
            results = await dense_search(db, query_vector, document_id=doc_id)
        assert results == []
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_dense_search_document_id_filters_to_one_document() -> None:
    embedder = Embedder(_MODEL)
    vectors = embedder.embed_batch(["identical content"])
    doc_a, chunks_a = await make_document_with_chunks(
        ["identical content"], embeddings=vectors
    )
    doc_b, chunks_b = await make_document_with_chunks(
        ["identical content"], embeddings=vectors
    )
    try:
        query_vector = embedder.embed_batch(["identical content"])[0]
        async with async_session_factory() as db:
            results = await dense_search(db, query_vector, document_id=doc_a)

        assert [r.chunk_id for r in results] == chunks_a
    finally:
        await delete_document(doc_a)
        await delete_document(doc_b)


@pytest.mark.asyncio
async def test_dense_search_respects_limit() -> None:
    embedder = Embedder(_MODEL)
    texts = [f"Distinct sentence number {i} about topic {i}." for i in range(5)]
    vectors = embedder.embed_batch(texts)
    doc_id, _ = await make_document_with_chunks(texts, embeddings=vectors)

    try:
        query_vector = embedder.embed_batch(["topic 2"])[0]
        async with async_session_factory() as db:
            results = await dense_search(
                db, query_vector, document_id=doc_id, limit=2
            )
        assert len(results) == 2
    finally:
        await delete_document(doc_id)
