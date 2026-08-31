from docmind.chunking.strategy import ChunkingStrategy, chunk_document
from docmind.extraction.models import ExtractedPage, ExtractionResult


def _extraction() -> ExtractionResult:
    text = "First paragraph.\n\nSecond paragraph with more words in it than the first."
    return ExtractionResult(text=text, pages=[ExtractedPage(page_number=1, text=text)])


def test_chunk_document_dispatches_to_structural_by_default() -> None:
    chunks = chunk_document(_extraction())
    assert len(chunks) >= 1


def test_chunk_document_dispatches_to_each_named_strategy() -> None:
    for strategy in ChunkingStrategy:
        chunks = chunk_document(_extraction(), strategy=strategy, target_tokens=10)
        assert len(chunks) >= 1
