import pytest

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.text import extract_text


def test_extract_text_decodes_utf8() -> None:
    result = extract_text(b"Hello DocMind")

    assert result.text == "Hello DocMind"
    assert result.metadata["char_count"] == len("Hello DocMind")
    assert result.pages[0].text == "Hello DocMind"


def test_extract_text_rejects_invalid_utf8() -> None:
    # A real failure mode: someone renames a binary file to .txt.
    invalid_utf8 = b"\xff\xfe\x00\x01not really text"

    with pytest.raises(CorruptDocumentError):
        extract_text(invalid_utf8)
