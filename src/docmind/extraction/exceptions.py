"""Exceptions raised by the extraction layer.

Kept distinct from generic Exception so the caller (the background
processing task) can tell "this file type isn't supported yet" apart
from "this file claims to be a PDF but is corrupt" — the two deserve
different error messages shown to a user.
"""


class ExtractionError(Exception):
    """Base class for all extraction failures."""


class UnsupportedDocumentTypeError(ExtractionError):
    """Raised when no extractor is registered for a file's type."""


class CorruptDocumentError(ExtractionError):
    """Raised when a file matches a known type but can't be parsed.

    Examples: a .pdf that isn't valid PDF bytes, a .xlsx that isn't a
    real zip/OOXML archive, a truncated download.
    """
