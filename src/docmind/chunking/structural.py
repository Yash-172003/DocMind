"""Structural chunking — use document structure as chunk boundaries.

Prefers real structural markers (Word "Heading 1" styles, via
ExtractionResult.headings) when the format provides them, and falls
back to paragraph boundaries (blank-line-separated) when it doesn't —
which today means every format except Word, since neither PDF glyph
positions nor plain text carry section markers we can trust yet. This
is a deliberate, documented limitation rather than a heuristic that
pretends to detect headings from font size or ALL-CAPS lines, which is
far less reliable and easy to get wrong silently.

Paragraphs/sections are grouped into chunks up to a token budget, same
idea as semantic chunking, but the break points come from actual
document structure instead of a similarity score.
"""

from docmind.chunking.models import TextChunk
from docmind.chunking.tokens import estimate_token_count, tokens_to_chars
from docmind.extraction.models import ExtractionResult, Heading


def _sections_from_headings(text: str, headings: list[Heading]) -> list[str]:
    """Split text at heading boundaries; each section starts at a heading."""
    offsets = sorted(h.char_offset for h in headings)
    sections: list[str] = []
    if offsets[0] > 0:
        sections.append(text[: offsets[0]])
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else len(text)
        sections.append(text[start:end])
    return [s.strip() for s in sections if s.strip()]


def _paragraphs(text: str) -> list[str]:
    # Extractors preserve source files byte-for-byte (text.py decodes raw
    # bytes with no newline translation), so a Windows-authored .txt file
    # has literal "\r\n\r\n" between paragraphs, not "\n\n". Normalize
    # here rather than in extraction, which should stay a faithful copy
    # of the source — this is a structural-chunking concern only.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [p.strip() for p in normalized.split("\n\n") if p.strip()]


def _flush(buffer_parts: list[str], page_number: int) -> TextChunk | None:
    if not buffer_parts:
        return None
    text = "\n\n".join(buffer_parts)
    return TextChunk(
        text=text,
        token_count=estimate_token_count(text),
        page_numbers=[page_number],
    )


def chunk_structural(
    extraction: ExtractionResult,
    target_tokens: int = 512,
) -> list[TextChunk]:
    """Group structural units (sections or paragraphs) up to a token budget.

    Note: a chunk never spans a page boundary here — unlike fixed-size
    and semantic chunking, which can (a section rarely needs to). If a
    single section/paragraph itself exceeds the budget, it becomes one
    oversized chunk rather than being recursively split further.
    """
    budget_chars = tokens_to_chars(target_tokens)
    use_headings = len(extraction.pages) == 1 and bool(extraction.headings)

    chunks: list[TextChunk] = []

    for page in extraction.pages:
        units = (
            _sections_from_headings(page.text, extraction.headings)
            if use_headings
            else _paragraphs(page.text)
        )

        buffer_parts: list[str] = []
        buffer_len = 0

        for unit in units:
            if buffer_parts and buffer_len + len(unit) > budget_chars:
                chunk = _flush(buffer_parts, page.page_number)
                if chunk is not None:
                    chunks.append(chunk)
                buffer_parts = []
                buffer_len = 0
            buffer_parts.append(unit)
            buffer_len += len(unit) + 2

        chunk = _flush(buffer_parts, page.page_number)
        if chunk is not None:
            chunks.append(chunk)

    return chunks
