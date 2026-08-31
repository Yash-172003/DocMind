"""Dispatches a file to the right extractor based on its extension.

We key off the filename extension rather than the client-supplied
Content-Type header — browsers and HTTP clients are inconsistent about
what MIME type they send for the same file, but a ".pdf" extension is a
much stronger (though still not perfect) signal of actual content. This
is also why every extractor independently validates that the bytes it
receives actually parse as its format: an extension is a claim, not a
guarantee — see CorruptDocumentError.
"""

from pathlib import Path

from docmind.extraction.excel import extract_xlsx
from docmind.extraction.exceptions import UnsupportedDocumentTypeError
from docmind.extraction.models import ExtractionResult
from docmind.extraction.pdf import extract_pdf
from docmind.extraction.text import extract_text
from docmind.extraction.word import extract_docx

_EXTRACTORS_BY_SUFFIX = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".xlsx": extract_xlsx,
    ".txt": extract_text,
}


def extract(filename: str, data: bytes) -> ExtractionResult:
    """Extract structured content from raw file bytes.

    Raises UnsupportedDocumentTypeError if the extension isn't registered,
    or CorruptDocumentError (propagated from the underlying extractor) if
    the bytes don't actually parse as their claimed format.
    """
    suffix = Path(filename).suffix.lower()
    extractor = _EXTRACTORS_BY_SUFFIX.get(suffix)
    if extractor is None:
        raise UnsupportedDocumentTypeError(
            f"No extractor registered for file type '{suffix or '(no extension)'}'"
        )
    return extractor(data)
