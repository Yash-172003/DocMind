"""Sparse retrieval — exact lexical matching via Okapi BM25.

Vector similarity (dense.py) fails on specific lookups: "What is the
total for PO-2024-1234?" needs an exact string match, not "something
semantically similar to a purchase order." Sparse retrieval is the
fix — it finds chunks containing the actual query terms.

We deliberately don't use Postgres's own ts_rank()/ts_rank_cd() for
scoring, even though we use its GIN-indexed tsvector column to find
candidates fast. Those functions exist and would work, but they aren't
BM25 (different formula, different tuning) — computing real BM25 by
hand here is the point: it's what "read the Okapi BM25 paper, understand
the scoring algorithm" (this week's roadmap reading) means in practice.

BM25, in one sentence: score a document higher for containing query
terms more times (term frequency), but with diminishing returns per
extra occurrence (the k1 saturation term), boosted for rare terms
across the whole corpus (IDF) and penalized for being longer than
average (the length-normalization term using b) — a long chunk
matching a term once is weaker evidence than a short chunk doing the
same.

Known limitation: term frequency here is computed by tokenizing raw
chunk text ourselves (a plain regex, no stemming), not from Postgres's
own tsvector lexemes (which ARE stemmed — "running" indexes as "run").
The GIN index (stemmed) is only used to find candidates; scoring
happens in Python on raw words. A query for "running" can therefore
retrieve a chunk that only contains "run" (the index matches) but will
under-count its term frequency during scoring (BM25 sees "running" and
"run" as different terms). Acceptable at this project's scale — see
scripts/evaluate_retrieval.py for how this behaves in practice.
"""

import math
import re
import uuid
from collections import Counter

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.db.models import Chunk
from docmind.retrieval.models import ScoredChunk

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")

# Standard Okapi BM25 defaults from the original paper's follow-up work
# (Robertson & Zaragoza, 2009) — k1 controls term-frequency saturation,
# b controls how strongly document length is penalized (0 = no penalty).
_K1 = 1.5
_B = 0.75


def _tokenize(text_value: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text_value)]


async def _document_frequency(db: AsyncSession, term: str) -> int:
    """How many chunks in the whole corpus contain this term at all."""
    result = await db.execute(
        select(func.count())
        .select_from(Chunk)
        .where(text("text_search @@ to_tsquery('english', :term)"))
        .params(term=term)
    )
    return result.scalar_one()


async def sparse_search(
    db: AsyncSession,
    query: str,
    limit: int = 20,
    candidate_pool: int = 100,
    document_id: uuid.UUID | None = None,
) -> list[ScoredChunk]:
    """Find and BM25-rank chunks matching any query term."""
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    # OR every term together for candidate retrieval (find chunks matching
    # ANY term — BM25 scoring below is what actually ranks by how well).
    # Built from our own regex-extracted words only, never raw user text,
    # so this can't be broken by tsquery operator characters in the input.
    composed_query = " | ".join(dict.fromkeys(query_terms))  # de-dup, keep order

    stmt = select(Chunk).where(
        text("text_search @@ to_tsquery('english', :composed_query)")
    ).params(composed_query=composed_query)
    if document_id is not None:
        stmt = stmt.where(Chunk.document_id == document_id)
    stmt = stmt.limit(candidate_pool)

    candidates = (await db.execute(stmt)).scalars().all()
    if not candidates:
        return []

    total_chunks = (
        await db.execute(select(func.count()).select_from(Chunk))
    ).scalar_one()
    # Postgres's AVG() returns NUMERIC, which asyncpg maps to
    # decimal.Decimal — must convert before mixing with float arithmetic.
    avg_length_raw = (
        await db.execute(select(func.avg(Chunk.token_count)))
    ).scalar_one()
    avg_length = float(avg_length_raw) if avg_length_raw is not None else 1.0

    unique_terms = list(dict.fromkeys(query_terms))
    doc_frequencies = {
        term: await _document_frequency(db, term) for term in unique_terms
    }
    idf = {
        term: math.log(
            (total_chunks - df + 0.5) / (df + 0.5) + 1
        )
        for term, df in doc_frequencies.items()
    }

    scored: list[ScoredChunk] = []
    for chunk in candidates:
        term_counts = Counter(_tokenize(chunk.text))
        length = chunk.token_count or len(term_counts) or 1
        score = 0.0
        for term in unique_terms:
            tf = term_counts.get(term, 0)
            if tf == 0:
                continue
            numerator = tf * (_K1 + 1)
            denominator = tf + _K1 * (1 - _B + _B * length / avg_length)
            score += idf[term] * (numerator / denominator)

        scored.append(
            ScoredChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page_numbers=chunk.page_numbers,
                section_heading=chunk.section_heading,
                score=score,
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:limit]
