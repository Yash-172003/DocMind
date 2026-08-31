"""PDF extraction.

Why PDF extraction can produce garbage: a PDF does not store paragraphs,
sentences, or even words — it stores individual glyphs positioned at
(x, y) coordinates on a page, the way a typesetting machine would place
metal type. There is no logical reading order encoded anywhere. Every
PDF text extractor is really solving a geometry problem: "given these
scattered glyph positions, guess the order a human would read them in."
That guess breaks on multi-column layouts, rotated text, and text placed
inside form fields or vector-drawn tables.

We use two different libraries, on purpose, not redundantly:
- pdfplumber (built on pdfminer.six): does careful geometric layout
  analysis, which is what makes its table extraction and coordinate data
  trustworthy. This is our primary extractor.
- pymupdf (fitz): a different, faster C-based parser (MuPDF). Its
  layout heuristics fail on different inputs than pdfplumber's, so a
  page that defeats one sometimes yields to the other. If both come
  back empty, the page is almost certainly a scanned image with no
  text layer at all, which neither library can help with — that needs
  OCR (Azure Document Intelligence, or a local OCR model), which is
  out of scope for this local-extraction pass and is flagged as a
  warning instead.

Real invoices found a second, worse failure mode than "empty": some
PDFs (in testing, ones exported from TallyPrime) return text that
LOOKS present but is scrambled — e.g. "P Po ri s v t a O te ff ic"
instead of "Post Office". This happens when a page lays out two blocks
of text (like two address columns) at overlapping y-coordinates;
pdfplumber sorts glyphs primarily by vertical position, so characters
from both blocks interleave on the same reconstructed line. pymupdf's
extraction handled these same pages correctly. "Empty" alone wasn't
enough to detect this — the check below also has to catch garbled
text and not just missing text.
"""

from io import BytesIO

import pdfplumber
import pymupdf

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.models import ExtractedPage, ExtractedTable, ExtractionResult

# Fraction of whitespace-separated tokens that are <=2 characters long.
# Measured on 5 real invoices: the 3 that extracted cleanly scored
# 0.14-0.22; the 2 with interleaved/scrambled text scored 0.39-0.40.
# 0.30 sits in the gap between those two clusters with margin on both
# sides. Below MIN_TOKENS_FOR_CHECK, short samples are skipped rather
# than risk a false positive on a genuinely short page.
_GARBLED_SHORT_TOKEN_RATIO = 0.30
_MIN_TOKENS_FOR_GARBLED_CHECK = 20


def _looks_garbled(text: str) -> bool:
    """Heuristic: does this text look like interleaved/scrambled glyphs?

    Column-interleaving garbling produces mostly 1-2 character
    "words" (fragments of real words sorted into the wrong order),
    where normal prose or invoice text does not.
    """
    tokens = text.split()
    if len(tokens) < _MIN_TOKENS_FOR_GARBLED_CHECK:
        return False
    short_tokens = sum(1 for t in tokens if len(t) <= 2)
    return (short_tokens / len(tokens)) >= _GARBLED_SHORT_TOKEN_RATIO


def _extract_page_text_with_pymupdf(data: bytes, page_number: int) -> str:
    """Fallback text extraction for a single page using pymupdf.

    page_number is 1-indexed to match pdfplumber's convention used
    throughout this module; pymupdf itself is 0-indexed internally.
    """
    # pymupdf ships py.typed but open()'s own stub is incomplete, hence the ignore.
    with pymupdf.open(stream=data, filetype="pdf") as doc:  # type: ignore[no-untyped-call]
        return doc[page_number - 1].get_text().strip()  # type: ignore[no-any-return]


def extract_pdf(data: bytes) -> ExtractionResult:
    """Extract text, tables, and metadata from PDF bytes."""
    try:
        pdf = pdfplumber.open(BytesIO(data))
    except Exception as exc:
        raise CorruptDocumentError(f"Could not open PDF: {exc}") from exc

    pages: list[ExtractedPage] = []
    tables: list[ExtractedTable] = []
    warnings: list[str] = []

    with pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            was_empty = not text
            was_garbled = bool(text) and _looks_garbled(text)

            if was_empty or was_garbled:
                fallback_text = _extract_page_text_with_pymupdf(data, i)
                if was_garbled and not _looks_garbled(fallback_text):
                    text = fallback_text
                    warnings.append(
                        f"page {i}: pdfplumber output looked scrambled "
                        "(likely overlapping text blocks); recovered via pymupdf"
                    )
                elif was_empty and fallback_text:
                    text = fallback_text
                    warnings.append(
                        f"page {i}: pdfplumber found no text; recovered via pymupdf"
                    )
                elif was_empty:
                    warnings.append(
                        f"page {i}: no extractable text in either engine "
                        "— likely a scanned image with no text layer (needs OCR)"
                    )
                elif was_garbled:
                    # pymupdf's fallback was garbled too — keep pdfplumber's
                    # text (still our best guess) but flag it for review.
                    warnings.append(
                        f"page {i}: pdfplumber output looked scrambled and "
                        "pymupdf did not recover it — text may be unreliable"
                    )

            pages.append(ExtractedPage(page_number=i, text=text))

            for raw_table in page.extract_tables():
                tables.append(
                    ExtractedTable(page_number=i, rows=list(raw_table))
                )

        metadata: dict[str, str | int | float | bool | None] = {
            "page_count": len(pdf.pages),
        }
        if pdf.metadata:
            for key in ("Title", "Author", "CreationDate", "Producer"):
                value = pdf.metadata.get(key)
                if value:
                    metadata[key.lower()] = str(value)

    full_text = "\n\n".join(p.text for p in pages if p.text)

    return ExtractionResult(
        text=full_text,
        pages=pages,
        tables=tables,
        metadata=metadata,
        warnings=warnings,
    )
