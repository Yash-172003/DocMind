"""Output shape shared by every retrieval method."""

import uuid

from pydantic import BaseModel


class ScoredChunk(BaseModel):
    """One chunk returned by a retrieval method, with its score.

    `score` is deliberately not normalized to a common scale across
    methods — cosine similarity (dense), BM25 (sparse), reciprocal
    rank (fusion), and a cross-encoder logit (reranking) all mean
    different things and aren't comparable to each other. Compare
    scores only within results from the same method.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    page_numbers: list[int] | None = None
    section_heading: str | None = None
    score: float
