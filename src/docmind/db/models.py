"""SQLAlchemy ORM models for DocMind.

Every table in the database is defined here as a Python class.
SQLAlchemy maps each class to a database table and each attribute
to a column — this is the ORM (Object-Relational Mapping) pattern.

Schema design:
    documents (parent)
        └── chunks (children — one document splits into many chunks)
                └── embedding stored directly on each chunk as a vector column

Indexes:
    - B-tree on documents.status — fast filtering by processing state
    - GIN on documents.metadata_ — search inside JSONB metadata
    - B-tree composite on chunks(document_id, chunk_index) for fast retrieval
    - HNSW on chunks.embedding — approximate nearest neighbor vector search
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class DocumentStatus(enum.StrEnum):
    """Processing status of a document.

    Inherits from StrEnum so it serializes cleanly to JSON.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Document(Base):
    """Represents an uploaded document in the system.

    This is the central entity of DocMind. Every document flows through
    these states: pending → processing → done (or failed).

    The metadata_ column uses JSONB to store flexible, schema-less data
    like page count, author, language, file size. We use a trailing
    underscore because 'metadata' is a reserved attribute in SQLAlchemy's
    DeclarativeBase.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB metadata — flexible key-value storage for document properties.
    # Examples: {"page_count": 42, "author": "Yash", "language": "en"}
    # We index this with GIN so PostgreSQL can search inside the JSON.
    metadata_: Mapped[dict | None] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=True, default=None
    )

    # Denormalized chunk count — avoids a COUNT(*) JOIN on every request.
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship — access document.chunks to get all child chunks.
    # cascade="all, delete-orphan" means: if a document is deleted,
    # all its chunks are automatically deleted too.
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )

    __table_args__ = (
        # B-tree index on status — fast filtering by processing state.
        # Without this, queries like WHERE status = 'done' would scan
        # every row in the table (Seq Scan).
        Index("ix_documents_status", "status"),
        # GIN index on metadata_ — enables fast @> (contains) queries
        # on JSONB. Example: WHERE metadata_ @> '{"language": "en"}'
        Index("ix_documents_metadata", "metadata_", postgresql_using="gin"),
    )


class Chunk(Base):
    """A chunk of text extracted from a document.

    Documents are split into chunks because:
    1. LLMs have context window limits — we can't feed a 500-page PDF at once
    2. Embeddings work better on focused, coherent text segments
    3. Citations need to point to specific passages, not entire documents

    Each chunk stores its own vector embedding for semantic search via pgvector.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # pgvector column — 1024 dimensions for BAAI/bge-large-en-v1.5.
    # This is where the semantic meaning of the chunk lives as a
    # high-dimensional vector. pgvector lets PostgreSQL search these
    # vectors for similarity without needing a separate vector database.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),
        nullable=True,
    )

    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Which pages this chunk came from — useful for citation grounding.
    # ARRAY(Integer) is a PostgreSQL-native array column.
    page_numbers: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer),
        nullable=True,
    )

    # The document section this chunk belongs to (e.g. "Findings"), when
    # the source format has real headings — only structural chunking on
    # Word documents populates this today. NULL for fixed-size/semantic
    # chunks and for structural chunks with no heading signal available.
    section_heading: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship back to parent document
    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        # Composite B-tree index — when we query "get all chunks for document X,
        # ordered by position", PostgreSQL can satisfy both the WHERE and ORDER BY
        # from this single index. Without it, it would do a Seq Scan + Sort.
        Index("ix_chunks_document_id_chunk_index", "document_id", "chunk_index"),
        # HNSW vector index for approximate nearest neighbor search.
        # HNSW (Hierarchical Navigable Small World) builds a multi-layer graph.
        # Tradeoff vs IVFFlat: HNSW uses more memory but works well from the
        # first insert (no training needed) and gives better recall.
        # vector_cosine_ops = cosine similarity, which is what bge-large uses.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
