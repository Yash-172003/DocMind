"""Output shape shared by every chunking strategy."""

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """One chunk produced by any chunking strategy.

    Deliberately doesn't carry chunk_index or embedding — those are
    assigned by the caller (chunk position in the final list, and the
    embedding model in Week 13-14), not by the chunking strategy itself.
    """

    text: str
    token_count: int
    page_numbers: list[int] = Field(default_factory=list)
