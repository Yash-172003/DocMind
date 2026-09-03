"""Cross-encoder reranking — the final, most accurate ranking pass.

Our embedding model (Week 13-14) is a bi-encoder: it embeds the query
and each chunk *independently*, then compares the two fixed vectors.
Fast (a chunk's embedding is computed once, ever, and reused for every
future query), but limited — the model never gets to look at the query
and the chunk together.

A cross-encoder does the opposite: it feeds the query and one chunk
into the model *together*, as a single input, so attention layers can
directly compare their tokens against each other. This is measurably
more accurate, but it means one forward pass per (query, chunk) pair —
far too slow to run against an entire corpus. So it's used only as a
final pass over the small candidate set hybrid search (dense + sparse +
RRF) already narrowed down to — "retrieve broadly and cheaply, rerank
narrowly and precisely," the standard two-stage retrieval pattern.

cross-encoder/ms-marco-MiniLM-L-6-v2 was trained specifically on query-
passage relevance (the MS MARCO passage ranking dataset), which is
exactly this task — unlike bge-large, which is a general-purpose
embedding model.
"""

from functools import lru_cache

from sentence_transformers import CrossEncoder

from docmind.retrieval.models import ScoredChunk


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str) -> CrossEncoder:
    # sentence-transformers ships py.typed but CrossEncoder's own __init__
    # stub is incomplete, hence the ignore (same situation as pymupdf.open()
    # in extraction/pdf.py).
    return CrossEncoder(model_name)  # type: ignore[no-any-return]


class Reranker:
    """Reranks a small candidate set by real query-chunk relevance."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def rerank(
        self, query: str, candidates: list[ScoredChunk], limit: int = 10
    ) -> list[ScoredChunk]:
        """Re-score and re-sort candidates; scores replace the input ones.

        A cross-encoder's raw output is an unbounded relevance logit,
        not a similarity/probability — it's only meaningful for sorting
        these candidates relative to each other, not for comparing
        against dense/sparse/RRF scores from other methods.
        """
        if not candidates:
            return []
        model = _load_cross_encoder(self.model_name)
        pairs = [(query, c.text) for c in candidates]
        raw_scores = model.predict(pairs, show_progress_bar=False)

        rescored = [
            c.model_copy(update={"score": float(s)})
            for c, s in zip(candidates, raw_scores, strict=True)
        ]
        rescored.sort(key=lambda c: c.score, reverse=True)
        return rescored[:limit]
