"""Fixed-size chunking — the naive baseline.

Slices the document into equal-sized, overlapping character windows,
completely ignoring sentence, paragraph, or section boundaries. This is
deliberately naive: implementing it is how you feel its failure mode
firsthand rather than take it on faith — chunks routinely start or end
mid-word, mid-sentence, or mid-table-row, because nothing here is told
what a "word" or a "sentence" even is. Compare its output against
chunk_semantic/chunk_structural on the same document to see it happen.
"""

from docmind.chunking.models import TextChunk
from docmind.chunking.tokens import estimate_token_count, tokens_to_chars
from docmind.extraction.models import ExtractionResult


def chunk_fixed_size(
    extraction: ExtractionResult,
    target_tokens: int = 512,
    overlap_tokens: int = 50,
) -> list[TextChunk]:
    """Split into fixed-size, overlapping character windows.

    A window's page_numbers lists every page whose text overlaps that
    window's character range at all — a window landing across a page
    boundary legitimately belongs to both pages.
    """
    spans: list[tuple[int, int, int]] = []  # (start, end, page_number)
    parts: list[str] = []
    offset = 0
    for page in extraction.pages:
        if not page.text:
            continue
        start = offset
        parts.append(page.text)
        offset += len(page.text)
        spans.append((start, offset, page.page_number))
        parts.append("\n\n")
        offset += 2

    full_text = "".join(parts)
    if not full_text.strip():
        return []

    window_chars = max(tokens_to_chars(target_tokens), 1)
    overlap_chars = min(max(tokens_to_chars(overlap_tokens), 0), window_chars - 1)
    step = window_chars - overlap_chars

    chunks: list[TextChunk] = []
    pos = 0
    while pos < len(full_text):
        window = full_text[pos : pos + window_chars]
        if window.strip():
            window_end = pos + len(window)
            pages_covered = sorted(
                {p for (s, e, p) in spans if s < window_end and e > pos}
            )
            chunks.append(
                TextChunk(
                    text=window,
                    token_count=estimate_token_count(window),
                    page_numbers=pages_covered,
                )
            )
        pos += step

    return chunks
