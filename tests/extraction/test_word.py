from io import BytesIO

import pytest
from docx import Document as DocxDocument

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.word import extract_docx
from tests.helpers import build_docx


def test_extract_docx_paragraphs() -> None:
    data = build_docx(["First paragraph.", "Second paragraph."])

    result = extract_docx(data)

    assert "First paragraph." in result.text
    assert "Second paragraph." in result.text
    assert result.text.index("First") < result.text.index("Second")
    assert result.tables == []


def test_extract_docx_table() -> None:
    data = build_docx(
        ["Invoice summary"],
        table_rows=[["Item", "Qty"], ["Widget", "3"]],
    )

    result = extract_docx(data)

    assert len(result.tables) == 1
    assert result.tables[0].rows == [["Item", "Qty"], ["Widget", "3"]]
    # Table content should also appear in the flattened text.
    assert "Widget" in result.text


def test_extract_docx_reading_order_preserved() -> None:
    doc = DocxDocument()
    doc.add_paragraph("Before table")
    table = doc.add_table(rows=1, cols=1)
    table.rows[0].cells[0].text = "Inside table"
    doc.add_paragraph("After table")
    buffer = BytesIO()
    doc.save(buffer)

    result = extract_docx(buffer.getvalue())

    before_idx = result.text.index("Before table")
    table_idx = result.text.index("Inside table")
    after_idx = result.text.index("After table")
    assert before_idx < table_idx < after_idx


def test_extract_docx_corrupt_bytes_raises() -> None:
    with pytest.raises(CorruptDocumentError):
        extract_docx(b"not a real docx file")
