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
from docmind.extraction.models import (
    ExtractedPage,
    ExtractedTable,
    ExtractionResult,
    Heading,
)


def _heading_level(style_name: str) -> int | None:
    """Map a paragraph style name to a heading level, or None if it isn't one.

    Word's built-in styles are named "Heading 1".."Heading 9" and "Title"
    (treated as level 0, above "Heading 1"). Custom/renamed styles won't
    match — that's a real limitation of style-based heading detection,
    not something we try to guess around.
    """
    if style_name == "Title":
        return 0
    if style_name.startswith("Heading "):
        level_str = style_name.removeprefix("Heading ").strip()
        if level_str.isdigit():
            return int(level_str)
    return None


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
    headings: list[Heading] = []
    offset = 0

    # Walk the document body in reading order so tables land where they
    # actually appear instead of being collected separately at the end.
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, doc)
            if paragraph.text.strip():
                level = _heading_level(paragraph.style.name if paragraph.style else "")
                if level is not None:
                    headings.append(
                        Heading(
                            text=paragraph.text, level=level, char_offset=offset
                        )
                    )
                text_parts.append(paragraph.text)
                offset += len(paragraph.text) + 2  # +2 for the "\n\n" joiner
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            tables.append(ExtractedTable(page_number=None, rows=rows))
            table_text = "\n".join(" | ".join(cell for cell in row) for row in rows)
            text_parts.append(table_text)
            offset += len(table_text) + 2

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
        headings=headings,
        metadata=metadata,
    )
