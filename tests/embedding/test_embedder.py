"""Embedder tests use a small model (all-MiniLM-L6-v2, 384 dims, ~90MB),
not the production BAAI/bge-large-en-v1.5 (1024 dims, ~1.3GB) — the
Embedder class takes model_name as a constructor argument specifically
so tests aren't forced to download/run the full production model.
Model loading is cached by name (see _load_model's lru_cache), so this
downloads once and every test after the first reuses it from memory.
"""

import math

from docmind.embedding.embedder import Embedder

_TEST_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def test_embed_batch_returns_one_vector_per_text() -> None:
    embedder = Embedder(_TEST_MODEL)

    vectors = embedder.embed_batch(["hello world", "goodbye world", "third text"])

    assert len(vectors) == 3


def test_embed_batch_vectors_match_model_dimension() -> None:
    embedder = Embedder(_TEST_MODEL)

    vectors = embedder.embed_batch(["hello world"])

    assert len(vectors[0]) == embedder.dimension == 384


def test_embed_batch_vectors_are_normalized() -> None:
    # normalize_embeddings=True should give every vector unit length —
    # this is what makes cosine similarity reduce to a plain dot product,
    # which is what pgvector's HNSW index (vector_cosine_ops) expects.
    embedder = Embedder(_TEST_MODEL)

    vectors = embedder.embed_batch(["some arbitrary sentence to embed"])

    assert math.isclose(_norm(vectors[0]), 1.0, abs_tol=1e-4)


def test_embed_batch_is_nearly_identical_alone_or_within_a_batch() -> None:
    # Batching is meant to be a performance optimization, not a behavior
    # change — but it isn't bit-for-bit identical in practice. Batching
    # pads shorter sequences to the longest one in the batch, which
    # changes the shape of the underlying matrix multiplications, which
    # changes floating-point summation order — and floating-point
    # addition isn't associative. This is a real, well-documented
    # numerical artifact of batched neural network inference, not a bug:
    # the two vectors should be extremely close, not exactly equal.
    embedder = Embedder(_TEST_MODEL)

    alone = embedder.embed_batch(["the quick brown fox"])
    in_batch = embedder.embed_batch(
        ["an unrelated sentence", "the quick brown fox", "another unrelated one"]
    )

    max_diff = max(abs(a - b) for a, b in zip(alone[0], in_batch[1], strict=True))
    assert max_diff < 1e-4


def test_embed_batch_empty_input_returns_empty_output() -> None:
    embedder = Embedder(_TEST_MODEL)

    assert embedder.embed_batch([]) == []


def test_embed_batch_similar_texts_are_more_similar_than_unrelated_ones() -> None:
    # A real semantic sanity check, not just a shape check: two sentences
    # about the same topic should have higher cosine similarity (here,
    # just a dot product since vectors are normalized) than two sentences
    # about unrelated topics.
    embedder = Embedder(_TEST_MODEL)

    cat_a, cat_b, unrelated = embedder.embed_batch(
        [
            "The cat sat on the warm windowsill.",
            "A kitten was sleeping in the sun.",
            "Quarterly revenue grew by twelve percent.",
        ]
    )

    def dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert dot(cat_a, cat_b) > dot(cat_a, unrelated)


def test_model_is_cached_across_embedder_instances() -> None:
    # Loading model weights from disk is the expensive part — a second
    # Embedder for the same model name must not reload them.
    from docmind.embedding.embedder import _load_model

    model_a = _load_model(_TEST_MODEL)
    model_b = _load_model(_TEST_MODEL)

    assert model_a is model_b
