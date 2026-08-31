import pytest

from docmind.extraction.excel import extract_xlsx
from docmind.extraction.exceptions import CorruptDocumentError
from tests.helpers import build_xlsx


def test_extract_xlsx_single_sheet() -> None:
    data = build_xlsx({"Sheet1": [["Name", "Amount"], ["Acme Corp", 1500]]})

    result = extract_xlsx(data)

    assert len(result.pages) == 1
    assert "Acme Corp" in result.text
    assert result.metadata["sheet_count"] == 1
    assert result.metadata["sheet_names"] == "Sheet1"


def test_extract_xlsx_multiple_sheets() -> None:
    data = build_xlsx(
        {
            "Invoices": [["ID", "Total"], ["INV-1", 100]],
            "Vendors": [["Name"], ["Acme"]],
        }
    )

    result = extract_xlsx(data)

    assert len(result.pages) == 2
    assert len(result.tables) == 2
    assert result.tables[0].rows == [["ID", "Total"], ["INV-1", "100"]]
    assert result.tables[1].rows == [["Name"], ["Acme"]]


def test_extract_xlsx_empty_sheet_produces_warning() -> None:
    data = build_xlsx({"Empty": [[]]})

    result = extract_xlsx(data)

    assert any("empty" in w for w in result.warnings)


def test_extract_xlsx_corrupt_bytes_raises() -> None:
    with pytest.raises(CorruptDocumentError):
        extract_xlsx(b"not a real xlsx file")
