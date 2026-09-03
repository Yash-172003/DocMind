"""Document management endpoints.

Architectural decision: Background tasks vs Celery.
FastAPI has a built-in BackgroundTasks system. For now, we use it because
it's simple and doesn't require Redis or a separate worker process.
The tradeoff: if the FastAPI server crashes mid-processing, the task is
lost. In Phase 4, we will upgrade to a proper queue (Celery + Redis)
for reliability. But for now, this teaches the pattern correctly.
"""

import uuid

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.api.deps import get_db, verify_api_key
from docmind.api.v1.schemas.document import (
    ChunkResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from docmind.chunking.strategy import chunk_document
from docmind.core.config import settings
from docmind.core.storage import delete_upload, read_upload, save_upload
from docmind.db.models import Chunk, Document, DocumentStatus
from docmind.embedding.embedder import Embedder
from docmind.extraction.exceptions import ExtractionError
from docmind.extraction.router import extract

logger = structlog.get_logger()

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(verify_api_key)],
)


async def process_document(document_id: uuid.UUID, db: AsyncSession) -> None:
    """Extract a document's content as a background task.

    1. Mark as processing
    2. Read the saved upload bytes and run them through the extraction
       layer (docmind.extraction) based on file extension
    3. Store the extracted text/metadata and mark as done — or mark as
       failed with a clear reason, never crash the worker
    """
    try:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        await db.commit()
        logger.info("document_processing_started", document_id=str(document_id))

        data = read_upload(document_id, document.filename)
        extraction = extract(document.filename, data)

        document.content = extraction.text
        metadata: dict[str, object] = dict(extraction.metadata)
        if extraction.warnings:
            metadata["warnings"] = extraction.warnings
        if extraction.tables:
            # Kept as raw structured grids (not flattened into `content`)
            # so column alignment survives — later consumers (the audit
            # agent in Phase 2) need real rows, not reflowed prose.
            metadata["tables"] = [t.model_dump() for t in extraction.tables]
        document.metadata_ = metadata

        chunks = chunk_document(extraction, strategy=settings.chunking_strategy)

        # One batch call for every chunk in this document, not one call
        # per chunk — see docmind.embedding.embedder and
        # scripts/measure_embedding_batching.py for why that matters.
        embedder = Embedder(settings.embedding_model)
        vectors = embedder.embed_batch(
            [chunk.text for chunk in chunks],
            batch_size=settings.embedding_batch_size,
        )

        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk.text,
                    embedding=vector,
                    token_count=chunk.token_count,
                    page_numbers=chunk.page_numbers or None,
                    section_heading=chunk.section_heading,
                )
            )
        document.chunk_count = len(chunks)

        document.status = DocumentStatus.DONE
        await db.commit()
        logger.info(
            "document_processing_complete",
            document_id=str(document_id),
            warnings=extraction.warnings,
            chunk_count=len(chunks),
        )

    except ExtractionError as e:
        document = (
            await db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            await db.commit()
        logger.warning(
            "document_extraction_failed",
            document_id=str(document_id),
            error=str(e),
        )

    except Exception as e:
        document = (
            await db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if document is not None:
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            await db.commit()
        logger.error(
            "document_processing_failed",
            document_id=str(document_id),
            error=str(e),
        )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a document for processing.

    Returns immediately with a job ID (HTTP 202 Accepted).
    The actual processing happens in the background.
    """
    document = Document(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # UploadFile's stream is tied to this request, so the bytes must be
    # saved to disk now — the background task runs after this handler
    # has already returned and the stream is gone.
    content = await file.read()
    save_upload(document.id, document.filename, content)

    logger.info(
        "document_uploaded",
        document_id=str(document.id),
        filename=document.filename,
    )

    # Queue background processing with its own DB session
    from docmind.db.base import async_session_factory

    async def _process() -> None:
        async with async_session_factory() as bg_session:
            await process_document(document.id, bg_session)

    background_tasks.add_task(_process)

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        message="Document uploaded. Processing started.",
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Check the processing status of a document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentStatusResponse.model_validate(document)


@router.get("/{document_id}/content", response_model=DocumentResponse)
async def get_document_content(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get the full content of a processed document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document from the system."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    await db.delete(document)
    await db.commit()
    delete_upload(document_id)
    logger.info("document_deleted", document_id=str(document_id))


@router.get("/{document_id}/chunks", response_model=list[ChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ChunkResponse]:
    """Get all chunks for a document, ordered by chunk index."""
    # First verify the document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Fetch chunks ordered by position
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    chunks = result.scalars().all()
    return [ChunkResponse.model_validate(c) for c in chunks]
