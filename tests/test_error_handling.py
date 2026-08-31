"""Cross-cutting error-handling guarantees, not covered by the
happy-path/known-failure tests elsewhere:
- process_document's generic `except Exception` branch (an unexpected
  failure that isn't an ExtractionError should still fail the document
  cleanly, not crash the background task)
- main.py's global exception handler (an unhandled exception anywhere
  in a route should return clean JSON, never a raw traceback)
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.api.deps import get_db
from docmind.api.v1.endpoints.documents import process_document
from docmind.core.config import settings
from docmind.db.base import async_session_factory
from docmind.db.models import Document, DocumentStatus
from docmind.main import app


@pytest.mark.asyncio
async def test_process_document_handles_unexpected_exception() -> None:
    # Realistic failure mode: the DB row exists (upload succeeded) but
    # the file is missing from disk when processing runs — e.g. cleaned
    # up externally between upload and processing. read_upload raises
    # FileNotFoundError, which is NOT an ExtractionError, so this is the
    # only test exercising the generic `except Exception` branch — the
    # actual "never crash the worker" guarantee, distinct from the
    # extraction-specific failure paths already covered elsewhere.
    async with async_session_factory() as db:
        document = Document(
            filename="never_saved.txt",
            content_type="text/plain",
            status=DocumentStatus.PENDING,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        document_id = document.id

    async with async_session_factory() as db:
        await process_document(document_id, db)  # file was never saved

    async with async_session_factory() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        refreshed = result.scalar_one()
        assert refreshed.status == DocumentStatus.FAILED
        assert refreshed.error_message is not None
        await db.delete(refreshed)
        await db.commit()


@pytest.mark.asyncio
async def test_process_document_returns_quietly_if_document_vanished() -> None:
    # Defensive check for a real race: the document could be deleted
    # between the upload request queuing this background task and the
    # task actually running. process_document must not raise — it
    # should just return, since there's nothing left to update.
    async with async_session_factory() as db:
        await process_document(uuid.uuid4(), db)  # no such document exists


@pytest.mark.asyncio
async def test_global_exception_handler_returns_clean_json() -> None:
    async def broken_get_db() -> AsyncGenerator[AsyncSession, None]:
        raise RuntimeError("simulated unexpected failure")
        yield  # pragma: no cover — unreachable, satisfies the generator type

    app.dependency_overrides[get_db] = broken_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"X-API-Key": settings.api_key},
        ) as client:
            response = await client.get(f"/api/v1/documents/{uuid.uuid4()}/status")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
