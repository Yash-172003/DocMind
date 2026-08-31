"""Structured representation returned by every document extractor.

Every format (PDF, Word, Excel, plain text) is different internally, but
downstream code (chunking, embedding, citation grounding in later phases)
should not need to know which extractor produced a result. Every extractor
in this package returns the same ExtractionResult shape regardless of
input format.
"""

from pydantic import BaseModel, Field


class ExtractedTable(BaseModel):
    """A table found inside a document, as rows of cell strings.

    Kept separate from plain text because tables lose their structure
    (columns, alignment) if flattened into a paragraph of text — citation
    grounding and audit workflows in later phases need the grid intact.
    """

    page_number: int | None = None
    rows: list[list[str | None]]


class ExtractedPage(BaseModel):
    """One page (PDF) or one sheet (Excel) worth of extracted text."""

    page_number: int
    text: str


class Heading(BaseModel):
    """A structural heading found in a document, with its position.

    char_offset indexes into ExtractionResult.text (the concatenated
    full document), not any single page — this lets structural chunking
    find section boundaries the same way regardless of source format.
    """

    text: str
    level: int
    char_offset: int


class ExtractionResult(BaseModel):
    """Unified output of any document extractor.

    text: all pages/sheets concatenated — a convenience for callers that
        don't care about page boundaries yet (e.g. this week's naive
        "store the whole thing in Document.content" pipeline).
    pages: per-page/per-sheet text, needed later for citation grounding
        (Phase 1, Week 17-18) where an answer must point at a specific page.
    tables: every table found, independent of which page it came from.
    headings: structural markers (e.g. Word "Heading 1" paragraph styles)
        that structural chunking uses as natural section boundaries.
        Empty when the format has no reliable heading signal (PDF, plain
        text) — structural chunking falls back to paragraph boundaries
        in that case rather than guessing at structure that isn't there.
    metadata: format-specific facts (page_count, author, sheet_names, ...).
    warnings: non-fatal problems worth surfacing (e.g. "page 4 has no
        extractable text — likely a scanned image").
    """

    text: str
    pages: list[ExtractedPage] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    headings: list[Heading] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    warnings: list[str] = Field(default_factory=list)
