import uuid

from docmind.retrieval.models import ScoredChunk
from docmind.retrieval.reranker import Reranker

_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _chunk(text: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        text=text,
        score=0.0,
    )


def test_reranker_ranks_relevant_passage_higher() -> None:
    reranker = Reranker(_MODEL)
    query = "What is the capital of France?"
    irrelevant = _chunk("Bananas are a good source of potassium.")
    relevant = _chunk("Paris is the capital and most populous city of France.")

    results = reranker.rerank(query, [irrelevant, relevant])

    assert results[0].text == relevant.text
    assert results[0].score > results[1].score


def test_reranker_empty_candidates_returns_empty() -> None:
    reranker = Reranker(_MODEL)
    assert reranker.rerank("query", []) == []


def test_reranker_respects_limit() -> None:
    reranker = Reranker(_MODEL)
    candidates = [
        _chunk(f"Sentence number {i} about various topics.") for i in range(5)
    ]

    results = reranker.rerank("various topics", candidates, limit=2)

    assert len(results) == 2


def test_reranker_model_is_cached_across_instances() -> None:
    from docmind.retrieval.reranker import _load_cross_encoder

    model_a = _load_cross_encoder(_MODEL)
    model_b = _load_cross_encoder(_MODEL)

    assert model_a is model_b
