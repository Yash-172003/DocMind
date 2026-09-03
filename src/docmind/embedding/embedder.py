"""Turns chunk text into vectors for semantic search.

What an embedding actually is: a fixed-length list of floating point
numbers (1024 of them, for the model below) positioned in a high-
dimensional space such that texts with similar *meaning* end up close
together, measured by cosine similarity — the cosine of the angle
between two vectors, ranging from -1 (opposite) to 1 (identical
meaning). This is what "semantic search" means mechanically: embed the
query the same way, then find chunks whose vectors have the highest
cosine similarity to it.

Model choice — BAAI/bge-large-en-v1.5 (1024 dimensions), not a smaller
or hosted alternative:
- all-MiniLM-L6-v2 (384 dims) is faster and smaller, but a noticeably
  weaker general-purpose model — fine for a demo, not for production
  retrieval quality.
- OpenAI's text-embedding-3-small is a hosted API: it costs money per
  call, sends your document contents to a third party, and adds
  network latency to every chunk. bge-large runs locally, free, and
  keeps documents on this machine — the right tradeoff for an
  enterprise document intelligence tool where data privacy matters.
- Domain matters more than model size: a general-purpose embedding
  model (any of the above) will blur together financial/legal terms
  that mean very different things in context ("consideration" in a
  contract vs. everyday English). bge-large isn't domain-tuned either,
  but it's the strongest free local option before that becomes a
  concern worth solving directly (e.g. fine-tuning, in a later phase).

Batching: sentence-transformers' encode() already batches internally
(the whole point of using a real ML library instead of calling a model
one input at a time) — see scripts/measure_embedding_batching.py for
the measured difference. Model loading itself is the expensive part
(reading ~1.3GB of weights from disk into memory), so it's cached by
model name and loaded once, not once per Embedder instance.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class Embedder:
    """Embeds text using a configurable sentence-transformers model.

    The model name is a constructor argument, not hardcoded, so tests
    can use a much smaller model (see tests/embedding/) without waiting
    on or downloading the full production model, while the real
    pipeline uses settings.embedding_model (BAAI/bge-large-en-v1.5).
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        """Vector length this model produces (1024 for bge-large-en-v1.5)."""
        dim = _load_model(self.model_name).get_embedding_dimension()
        if dim is None:
            raise RuntimeError(
                f"Model {self.model_name!r} does not report a fixed "
                "embedding dimension"
            )
        return dim

    def embed_batch(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
        """Embed many texts in one call — never loop calling this per-text.

        normalize_embeddings=True L2-normalizes each vector to unit
        length, which BAAI's bge models are trained and evaluated
        against — cosine similarity on normalized vectors reduces to a
        plain dot product, which is also what pgvector's HNSW index
        (built with vector_cosine_ops back in Week 5-6) expects.
        """
        if not texts:
            return []
        model = _load_model(self.model_name)
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]
