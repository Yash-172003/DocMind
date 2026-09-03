import uuid

from docmind.retrieval.fusion import reciprocal_rank_fusion
from docmind.retrieval.models import ScoredChunk


def _chunk(chunk_id: uuid.UUID, score: float = 0.0) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        chunk_index=0,
        text="placeholder",
        score=score,
    )


def test_rrf_ignores_original_scores_uses_rank_only() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # 'a' has a tiny original score but ranks #1 in both lists.
    dense = [_chunk(a, score=0.01), _chunk(b, score=0.99)]
    sparse = [_chunk(a, score=0.01), _chunk(b, score=99.0)]

    fused = reciprocal_rank_fusion([dense, sparse])

    assert fused[0].chunk_id == a  # rank position won, not the raw score


def test_rrf_rewards_appearing_high_in_both_lists() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    dense = [_chunk(a), _chunk(b), _chunk(c)]  # a=1, b=2, c=3
    sparse = [_chunk(b), _chunk(a), _chunk(c)]  # b=1, a=2, c=3

    fused = reciprocal_rank_fusion([dense, sparse])
    scores = {c.chunk_id: c.score for c in fused}

    # a and b each hold rank {1,2} across the two lists (symmetric) —
    # exact tie. c is rank 3 in both — strictly lower than either.
    assert scores[a] == scores[b]
    assert scores[a] > scores[c]
    assert scores[a] == 1 / 61 + 1 / 62
    assert scores[c] == 1 / 63 + 1 / 63


def test_rrf_includes_chunks_from_only_one_list() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    dense = [_chunk(a)]
    sparse = [_chunk(b)]

    fused = reciprocal_rank_fusion([dense, sparse])

    assert {c.chunk_id for c in fused} == {a, b}


def test_rrf_respects_limit() -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    dense = [_chunk(i) for i in ids]

    fused = reciprocal_rank_fusion([dense], limit=2)

    assert len(fused) == 2


def test_rrf_empty_rankings_returns_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == []
