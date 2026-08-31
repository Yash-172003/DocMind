"""Plain text extraction — the trivial case, no parsing needed."""

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.models import ExtractedPage, ExtractionResult


def extract_text(data: bytes) -> ExtractionResult:
    """Decode plain text bytes as UTF-8."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorruptDocumentError(f"Not valid UTF-8 text: {exc}") from exc

    return ExtractionResult(
        text=text,
        pages=[ExtractedPage(page_number=1, text=text)],
        metadata={"char_count": len(text)},
    )
