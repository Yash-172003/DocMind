import pytest

from docmind.extraction.exceptions import UnsupportedDocumentTypeError
from docmind.extraction.router import extract


def test_extract_dispatches_by_extension() -> None:
    result = extract("notes.txt", b"hello from a text file")
    assert result.text == "hello from a text file"


def test_extract_unsupported_extension_raises() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        extract("archive.zip", b"PK\x03\x04")


def test_extract_no_extension_raises() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        extract("README", b"hello")


def test_extract_is_case_insensitive() -> None:
    result = extract("NOTES.TXT", b"still works")
    assert result.text == "still works"
