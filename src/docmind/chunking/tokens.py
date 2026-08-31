"""Token counting — approximate, on purpose, for now.

A real token count depends on the exact tokenizer of the model reading
the text (a BPE vocabulary, subword merges, etc.). We haven't committed
to an embedding model yet — that's Week 13-14 (BAAI/bge-large-en-v1.5).
Pulling in a real tokenizer now (tiktoken downloads its encoding file
over the network on first use; a HuggingFace tokenizer downloads from
the Hub) would mean chunking's test suite depends on internet access,
which is the same tradeoff we deliberately avoided with the
Unstructured library in Week 9-10.

len(text) // 4 is the standard rough English-text approximation (~4
characters per token for BPE-style tokenizers) — good enough to size
chunks consistently. This gets replaced with the real tokenizer once
Week 13-14 picks the embedding model.
"""

_CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_token_count(text: str) -> int:
    """Approximate the number of tokens in text. See module docstring."""
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


def tokens_to_chars(token_count: int) -> int:
    """Inverse of estimate_token_count — a character budget for a token target."""
    return token_count * _CHARS_PER_TOKEN_ESTIMATE
