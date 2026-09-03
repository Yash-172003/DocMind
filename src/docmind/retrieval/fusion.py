"""Reciprocal Rank Fusion — combine dense and sparse rankings.

Dense (cosine similarity) and sparse (BM25) scores live on completely
different scales — a cosine similarity of 0.7 and a BM25 score of 12.3
can't be averaged or compared directly. RRF sidesteps this: it ignores
the actual scores entirely and only looks at *rank position* within
each list. A chunk ranked #1 by both methods scores far higher than one
ranked #1 by only one method and unranked by the other — this is what
makes hybrid search outperform either method alone.

Formula: score(chunk) = sum, over every ranking it appears in, of
1 / (k + rank). k=60 is the constant from the original RRF paper
(Cormack et al., 2009) — it dampens the difference between e.g. rank 1
and rank 2 so one list's noise at the top doesn't dominate the fusion.
"""

import uuid

from docmind.retrieval.models import ScoredChunk

_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[ScoredChunk]],
    limit: int = 10,
) -> list[ScoredChunk]:
    """Merge multiple ranked chunk lists into one, by rank position only.

    Returned chunks carry the fused RRF score, not their original
    dense/sparse score — those aren't on comparable scales (see module
    docstring), so keeping one of them would misleadingly imply the
    fused ranking is "cosine similarity" or "BM25" when it's neither.
    """
    fused_scores: dict[uuid.UUID, float] = {}
    chunk_by_id: dict[uuid.UUID, ScoredChunk] = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            fused_scores[chunk.chunk_id] = fused_scores.get(
                chunk.chunk_id, 0.0
            ) + 1.0 / (_RRF_K + rank)
            chunk_by_id.setdefault(chunk.chunk_id, chunk)

    ranked_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
    return [
        chunk_by_id[cid].model_copy(update={"score": fused_scores[cid]})
        for cid in ranked_ids[:limit]
    ]
