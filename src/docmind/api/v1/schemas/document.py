"""Pydantic v2 schemas for document endpoints.

Architectural decision: We never return raw ORM models from our API.
Instead, we define explicit response schemas. This gives us:
1. Control over exactly which fields are exposed (security)
2. Automatic validation and serialization
3. Auto-generated API documentation in Swagger UI
4. A stable API contract even if the DB schema changes internally
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from docmind.db.models import DocumentStatus


class DocumentResponse(BaseModel):
    """Full document representation returned by the API."""

    id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    content: str | None = None
    error_message: str | None = None
    metadata_: dict[str, Any] | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    """Lightweight response for the status-check endpoint."""

    id: uuid.UUID
    filename: str
    status: DocumentStatus

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    """Returned immediately after upload — before processing finishes."""

    id: uuid.UUID
    filename: str
    status: DocumentStatus
    message: str


class ChunkResponse(BaseModel):
    """Response schema for a single chunk of a document."""

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int
    page_numbers: list[int] | None = None
    section_heading: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
