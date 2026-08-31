"""Word (.docx) extraction via python-docx.

Unlike PDF, a .docx file already stores logical structure — paragraphs
and tables are distinct XML elements, not scattered glyphs — so there is
no positional-reconstruction problem here. The extraction challenge for
Word documents is different: paragraphs and tables can be interleaved in
any order, and we want to preserve that reading order rather than
dumping all paragraphs first and all tables after.
"""

from io import BytesIO

from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from docmind.extraction.exceptions import CorruptDocumentError
from docmind.extraction.models import ExtractedPage, ExtractedTable, ExtractionResult


def extract_docx(data: bytes) -> ExtractionResult:
    """Extract text, tables, and metadata from .docx bytes.

    .docx has no fixed concept of "pages" — page breaks depend on font
    metrics and printer settings, which python-docx does not compute.
    So the whole document is returned as a single ExtractedPage.
    """
    try:
        doc = DocxDocument(BytesIO(data))
    except Exception as exc:
        raise CorruptDocumentError(f"Could not open Word document: {exc}") from exc

    text_parts: list[str] = []
    tables: list[ExtractedTable] = []

    # Walk the document body in reading order so tables land where they
    # actually appear instead of being collected separately at the end.
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, doc)
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            tables.append(ExtractedTable(page_number=None, rows=rows))
            text_parts.append(
                "\n".join(" | ".join(cell for cell in row) for row in rows)
            )

    full_text = "\n\n".join(text_parts)

    props = doc.core_properties
    metadata: dict[str, str | int | float | bool | None] = {
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(tables),
    }
    if props.author:
        metadata["author"] = props.author
    if props.title:
        metadata["title"] = props.title
    if props.created:
        metadata["created"] = props.created.isoformat()

    return ExtractionResult(
        text=full_text,
        pages=[ExtractedPage(page_number=1, text=full_text)],
        tables=tables,
        metadata=metadata,
    )
