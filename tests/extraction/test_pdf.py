import pymupdf
import pytest

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.pdf import _looks_garbled, extract_pdf
from tests.helpers import build_pdf


def test_extract_pdf_single_page_text() -> None:
    data = build_pdf(["Hello DocMind"])

    result = extract_pdf(data)

    assert "Hello DocMind" in result.text
    assert len(result.pages) == 1
    assert result.metadata["page_count"] == 1
    assert result.warnings == []


def test_extract_pdf_multiple_pages_preserve_order() -> None:
    data = build_pdf(["Page one content", "Page two content", "Page three content"])

    result = extract_pdf(data)

    assert len(result.pages) == 3
    assert result.pages[0].text.strip() == "Page one content"
    assert result.pages[1].text.strip() == "Page two content"
    assert result.pages[2].text.strip() == "Page three content"
    assert result.text.index("Page one") < result.text.index("Page two")
    assert result.text.index("Page two") < result.text.index("Page three")


def test_extract_pdf_blank_page_produces_warning() -> None:
    doc = pymupdf.open()
    doc.new_page()  # no text inserted — a genuinely empty page
    data: bytes = doc.tobytes()
    doc.close()

    result = extract_pdf(data)

    assert result.pages[0].text == ""
    assert len(result.warnings) == 1
    assert "no extractable text" in result.warnings[0]


def test_extract_pdf_corrupt_bytes_raises() -> None:
    with pytest.raises(CorruptDocumentError):
        extract_pdf(b"this is not a pdf file at all")


def test_looks_garbled_detects_interleaved_text() -> None:
    # Real example of pdfplumber output on a TallyPrime-exported invoice
    # whose address block was garbled by column interleaving.
    garbled = (
        "P Po ri s v t a O te ff ic L e im , G it a e u d t , a m Pl o B t u "
        "N dd o h . a 7 N , a S g e a c r, t o D r a 1 d 4 ri, 2 U , t N ta o"
    )
    assert _looks_garbled(garbled) is True


def test_looks_garbled_accepts_normal_prose() -> None:
    normal = (
        "Post Office, Gautam Buddha Nagar, Dadri, Uttar Pradesh, India, "
        "201305 State Name : Uttar Pradesh, Code : 09"
    )
    assert _looks_garbled(normal) is False


def test_looks_garbled_ignores_short_text() -> None:
    # Too few tokens to judge reliably — must not false-positive.
    assert _looks_garbled("P Po ri s v") is False


def test_extract_pdf_normal_layout_never_triggers_fallback() -> None:
    data = build_pdf(["Post Office, Gautam Buddha Nagar, Dadri, Uttar Pradesh"])

    result = extract_pdf(data)

    assert "Post Office" in result.text
    assert result.warnings == []
