"""Selects which chunking strategy runs, by name.

Kept as a thin dispatcher (not a class hierarchy or plugin registry)
because there are exactly three strategies, all fixed for the
foreseeable future — see Docs/DocMind.txt Week 11-12. This gets
revisited if that ever stops being true.
"""

import enum

from docmind.chunking.fixed_size import chunk_fixed_size
from docmind.chunking.models import TextChunk
from docmind.chunking.semantic import chunk_semantic
from docmind.chunking.structural import chunk_structural
from docmind.extraction.models import ExtractionResult


class ChunkingStrategy(enum.StrEnum):
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"


def chunk_document(
    extraction: ExtractionResult,
    strategy: ChunkingStrategy = ChunkingStrategy.STRUCTURAL,
    target_tokens: int = 512,
) -> list[TextChunk]:
    """Chunk an extraction result using the given strategy."""
    if strategy == ChunkingStrategy.FIXED_SIZE:
        return chunk_fixed_size(extraction, target_tokens=target_tokens)
    if strategy == ChunkingStrategy.SEMANTIC:
        return chunk_semantic(extraction, target_tokens=target_tokens)
    return chunk_structural(extraction, target_tokens=target_tokens)
