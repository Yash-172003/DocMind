"""Document management endpoints.

Architectural decision: Background tasks vs Celery.
FastAPI has a built-in BackgroundTasks system. For now, we use it because
it's simple and doesn't require Redis or a separate worker process.
The tradeoff: if the FastAPI server crashes mid-processing, the task is
lost. In Phase 4, we will upgrade to a proper queue (Celery + Redis)
for reliability. But for now, this teaches the pattern correctly.
"""

import asyncio
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
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from docmind.db.models import Document, DocumentStatus

logger = structlog.get_logger()

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(verify_api_key)],
)


async def simulate_document_processing(
    document_id: uuid.UUID, db: AsyncSession
) -> None:
    """Simulate document processing as a background task.

    In Phase 1, this will be replaced with real PDF/Word extraction.
    For now, it demonstrates the async background task pattern:
    1. Mark as processing
    2. Do work (simulated with sleep)
    3. Mark as done (or failed)
    """
    try:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            return

        document.status = DocumentStatus.PROCESSING
        await db.commit()
        logger.info("document_processing_started", document_id=str(document_id))

        # Simulate processing time
        await asyncio.sleep(3)

        document.content = f"Extracted content from {document.filename} (simulated)"
        document.status = DocumentStatus.DONE
        await db.commit()
        logger.info("document_processing_complete", document_id=str(document_id))

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

    logger.info(
        "document_uploaded",
        document_id=str(document.id),
        filename=document.filename,
    )

    # Queue background processing with its own DB session
    from docmind.db.base import async_session_factory

    async def _process() -> None:
        async with async_session_factory() as bg_session:
            await simulate_document_processing(document.id, bg_session)

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
    logger.info("document_deleted", document_id=str(document_id))
