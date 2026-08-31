from docmind.chunking.tokens import estimate_token_count, tokens_to_chars


def test_estimate_token_count_uses_four_chars_per_token() -> None:
    assert estimate_token_count("a" * 400) == 100


def test_estimate_token_count_never_returns_zero() -> None:
    assert estimate_token_count("") == 1
    assert estimate_token_count("hi") == 1


def test_tokens_to_chars_is_the_inverse_ratio() -> None:
    assert tokens_to_chars(100) == 400
    assert estimate_token_count("x" * tokens_to_chars(100)) == 100
