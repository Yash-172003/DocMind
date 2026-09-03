"""Output shape shared by every chunking strategy."""

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """One chunk produced by any chunking strategy.

    Deliberately doesn't carry chunk_index or embedding — those are
    assigned by the caller (chunk position in the final list, and the
    embedding model, respectively), not by the chunking strategy itself.
    """

    text: str
    token_count: int
    page_numbers: list[int] = Field(default_factory=list)
    # Only populated by structural chunking when a real heading (a Word
    # "Heading N" style) introduced this chunk's section — None for
    # fixed-size/semantic chunking, and for structural chunks that fall
    # back to plain paragraph boundaries (no heading signal available).
    section_heading: str | None = None
