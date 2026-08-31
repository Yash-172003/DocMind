from docmind.chunking.fixed_size import chunk_fixed_size
from docmind.extraction.models import ExtractedPage, ExtractionResult


def _extraction(pages: list[ExtractedPage]) -> ExtractionResult:
    text = "\n\n".join(p.text for p in pages)
    return ExtractionResult(text=text, pages=pages)


def test_fixed_size_cuts_mid_word_by_design() -> None:
    # This is the point of the naive baseline: with no overlap, a plain
    # character window has no idea "gamma" is a word and slices it in half.
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    extraction = _extraction([ExtractedPage(page_number=1, text=text)])

    chunks = chunk_fixed_size(extraction, target_tokens=3, overlap_tokens=0)

    assert chunks[0].text == "alpha beta g"  # cuts "gamma" into "g" + "amma"


def test_fixed_size_overlap_shares_characters_between_windows() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    extraction = _extraction([ExtractedPage(page_number=1, text=text)])

    chunks = chunk_fixed_size(extraction, target_tokens=3, overlap_tokens=1)

    assert chunks[0].text[-4:] == chunks[1].text[:4]


def test_fixed_size_tracks_pages_a_window_spans() -> None:
    extraction = _extraction(
        [
            ExtractedPage(page_number=1, text="A" * 10),
            ExtractedPage(page_number=2, text="B" * 10),
        ]
    )

    chunks = chunk_fixed_size(extraction, target_tokens=4, overlap_tokens=0)

    assert chunks[0].page_numbers == [1, 2]  # window straddles the boundary
    assert chunks[1].page_numbers == [2]


def test_fixed_size_empty_extraction_returns_no_chunks() -> None:
    extraction = ExtractionResult(text="", pages=[])
    assert chunk_fixed_size(extraction) == []


def test_fixed_size_skips_pages_with_no_text() -> None:
    # A blank page (e.g. a scanned image with no text layer) should be
    # skipped entirely rather than contributing an empty span.
    extraction = _extraction(
        [
            ExtractedPage(page_number=1, text=""),
            ExtractedPage(page_number=2, text="alpha beta gamma delta"),
        ]
    )

    chunks = chunk_fixed_size(extraction, target_tokens=10, overlap_tokens=0)

    assert len(chunks) == 1
    assert chunks[0].page_numbers == [2]
