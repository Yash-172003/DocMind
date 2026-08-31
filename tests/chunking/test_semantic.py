from docmind.chunking.semantic import chunk_semantic
from docmind.extraction.models import ExtractedPage, ExtractionResult


def _extraction(pages: list[ExtractedPage]) -> ExtractionResult:
    text = "\n\n".join(p.text for p in pages)
    return ExtractionResult(text=text, pages=pages)


def test_semantic_breaks_on_topic_shift_before_hitting_budget() -> None:
    cat_1 = "Cats are wonderful pets that purr loudly."
    cat_2 = "Cats like to chase mice around the house."
    physics_1 = "Quantum physics describes subatomic particles precisely."
    physics_2 = "Quantum particles exhibit strange probabilistic behavior often."
    page = ExtractedPage(
        page_number=1,
        text=" ".join([cat_1, cat_2, physics_1, physics_2]),
    )
    extraction = _extraction([page])

    # target_tokens=50 -> budget of 200 chars, comfortably larger than
    # either group, so the break has to come from the similarity check.
    chunks = chunk_semantic(extraction, target_tokens=50, similarity_threshold=0.1)

    assert len(chunks) == 2
    assert chunks[0].text == f"{cat_1} {cat_2}"
    assert chunks[1].text == f"{physics_1} {physics_2}"


def test_semantic_keeps_similar_sentences_together_across_pages() -> None:
    extraction = _extraction(
        [
            ExtractedPage(page_number=1, text="Cats are pets."),
            ExtractedPage(page_number=2, text="Cats are friendly."),
        ]
    )

    chunks = chunk_semantic(extraction, target_tokens=100)

    assert len(chunks) == 1
    assert chunks[0].page_numbers == [1, 2]


def test_semantic_respects_token_budget_even_without_topic_shift() -> None:
    # All sentences share vocabulary (never a topic shift), so only the
    # hard token budget should force a break.
    sentences = [f"Cats love sentence number {i} very much." for i in range(10)]
    page = ExtractedPage(page_number=1, text=" ".join(sentences))
    extraction = _extraction([page])

    chunks = chunk_semantic(extraction, target_tokens=20)  # 80-char budget

    assert len(chunks) > 1
    assert all(c.token_count <= 25 for c in chunks)  # allow small rounding slack


def test_semantic_empty_extraction_returns_no_chunks() -> None:
    extraction = ExtractionResult(text="", pages=[])
    assert chunk_semantic(extraction) == []


def test_semantic_handles_sentences_with_no_words() -> None:
    # Realistic in invoice line items: "10 250.00 25%." has zero
    # alphabetic tokens, so its term-frequency vector is empty —
    # cosine similarity against it must resolve to 0.0, not crash.
    page = ExtractedPage(
        page_number=1,
        text="This has real words in it. 10 250.00 25%. More real words follow.",
    )
    extraction = _extraction([page])

    chunks = chunk_semantic(extraction, target_tokens=100)

    assert len(chunks) >= 1
