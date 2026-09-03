"""Uses document_id filtering throughout so result lists are restricted
to each test's own inserted chunks — see helpers.py for why: BM25's
corpus-wide statistics (total chunk count, document frequency) can't be
isolated per test, but they apply as the same constant to every
candidate within one query, so relative ordering among controlled,
equal-length chunks is still fully deterministic.
"""

import pytest

from docmind.db.base import async_session_factory
from docmind.retrieval.sparse import sparse_search
from tests.retrieval.helpers import delete_document, make_document_with_chunks


@pytest.mark.asyncio
async def test_sparse_search_finds_chunk_with_matching_term() -> None:
    doc_id, chunk_ids = await make_document_with_chunks(
        [
            "The zylophant walked across the field slowly.",
            "Quarterly revenue grew significantly this year.",
        ]
    )
    try:
        async with async_session_factory() as db:
            results = await sparse_search(db, "zylophant", document_id=doc_id)

        assert [r.chunk_id for r in results] == [chunk_ids[0]]
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_sparse_search_no_matching_terms_returns_empty() -> None:
    doc_id, _ = await make_document_with_chunks(["Some ordinary sentence here."])
    try:
        async with async_session_factory() as db:
            results = await sparse_search(
                db, "zzznonexistentqueryterm", document_id=doc_id
            )
        assert results == []
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_sparse_search_higher_term_frequency_ranks_first() -> None:
    # Same word count in both, so length normalization is identical for
    # both — isolates the term-frequency effect specifically.
    high_tf = "zylophant zylophant zylophant walked across a distant green field"
    low_tf = "zylophant walked slowly across a distant green meadow today"
    doc_id, chunk_ids = await make_document_with_chunks([high_tf, low_tf])
    try:
        async with async_session_factory() as db:
            results = await sparse_search(db, "zylophant", document_id=doc_id)

        assert [r.chunk_id for r in results] == chunk_ids
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_sparse_search_document_id_filters_to_one_document() -> None:
    doc_a, chunks_a = await make_document_with_chunks(["zylophant lives here"])
    doc_b, chunks_b = await make_document_with_chunks(["zylophant lives there too"])
    try:
        async with async_session_factory() as db:
            results = await sparse_search(db, "zylophant", document_id=doc_a)

        assert [r.chunk_id for r in results] == chunks_a
    finally:
        await delete_document(doc_a)
        await delete_document(doc_b)


@pytest.mark.asyncio
async def test_sparse_search_matches_any_query_term_not_all() -> None:
    # BM25 is an OR over query terms, scored by how well each matches —
    # not a strict AND requiring every term to be present.
    doc_id, chunk_ids = await make_document_with_chunks(
        ["zylophant appears alone here", "quixotical appears alone here too"]
    )
    try:
        async with async_session_factory() as db:
            results = await sparse_search(
                db, "zylophant quixotical", document_id=doc_id
            )

        assert {r.chunk_id for r in results} == set(chunk_ids)
    finally:
        await delete_document(doc_id)


@pytest.mark.asyncio
async def test_sparse_search_empty_query_returns_empty() -> None:
    doc_id, _ = await make_document_with_chunks(["Some content here."])
    try:
        async with async_session_factory() as db:
            results = await sparse_search(db, "   ", document_id=doc_id)
        assert results == []
    finally:
        await delete_document(doc_id)
