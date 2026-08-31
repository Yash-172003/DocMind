"""Semantic chunking — group sentences by topical similarity.

Splits each page into sentences, then greedily groups consecutive
sentences into a chunk until either the token budget is hit, or the
next sentence looks topically unrelated to what's accumulated so far.
This implements the roadmap's "use embedding similarity to decide
breaks" with term-frequency (TF) vectors instead of a neural embedding
model: we haven't chosen an embedding model yet (that's Week 13-14),
and pulling one in now would mean downloading a multi-GB model just to
decide where a chunk boundary goes. TF vectors are a real, classical
(pre-neural) similarity technique — a legitimate stand-in, not a fake
one — and swappable for real embeddings later without changing this
module's structure or call signature.

Known limitation: sentence splitting is a plain regex, not a real
sentence tokenizer, so it mis-splits on abbreviations ("Mr. Smith" ->
two "sentences"). A real tokenizer (spaCy, NLTK) would fix this but
reintroduces the network-download dependency problem we deliberately
avoided with the Unstructured library in Week 9-10.
"""

import math
import re
from collections import Counter

from docmind.chunking.models import TextChunk
from docmind.chunking.tokens import estimate_token_count, tokens_to_chars
from docmind.extraction.models import ExtractionResult

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-zA-Z]+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _term_frequencies(text: str) -> Counter[str]:
    return Counter(w.lower() for w in _WORD_RE.findall(text))


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    # Every key in a Counter built from findall() has a count of at
    # least 1, so a non-empty Counter always has a positive norm —
    # only the emptiness check below is actually reachable, not a
    # separate zero-norm case.
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b)


def chunk_semantic(
    extraction: ExtractionResult,
    target_tokens: int = 512,
    similarity_threshold: float = 0.1,
) -> list[TextChunk]:
    """Group sentences into chunks, breaking early on a topic shift."""
    budget_chars = tokens_to_chars(target_tokens)
    min_break_chars = budget_chars // 4  # don't fragment into tiny chunks

    chunks: list[TextChunk] = []
    buffer_sentences: list[str] = []
    buffer_pages: set[int] = set()
    buffer_vector: Counter[str] = Counter()
    buffer_len = 0

    def flush() -> None:
        if not buffer_sentences:
            return
        text = " ".join(buffer_sentences)
        chunks.append(
            TextChunk(
                text=text,
                token_count=estimate_token_count(text),
                page_numbers=sorted(buffer_pages),
            )
        )
        buffer_sentences.clear()
        buffer_pages.clear()
        buffer_vector.clear()

    for page in extraction.pages:
        for sentence in _split_sentences(page.text):
            sentence_vector = _term_frequencies(sentence)

            if buffer_sentences:
                similarity = _cosine_similarity(buffer_vector, sentence_vector)
                would_exceed_budget = buffer_len + len(sentence) > budget_chars
                topic_shifted = (
                    similarity < similarity_threshold and buffer_len >= min_break_chars
                )
                if would_exceed_budget or topic_shifted:
                    flush()
                    buffer_len = 0

            buffer_sentences.append(sentence)
            buffer_pages.add(page.page_number)
            buffer_vector.update(sentence_vector)
            buffer_len += len(sentence) + 1

    flush()
    return chunks
