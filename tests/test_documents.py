from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from docmind.core.config import settings
from docmind.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": settings.api_key},
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_upload_document(client: AsyncClient) -> None:
    # We simulate a file upload using httpx
    files = {"file": ("test_doc.txt", b"Hello world", "text/plain")}
    response = await client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test_doc.txt"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_document_lifecycle(client: AsyncClient) -> None:
    # 1. Upload
    files = {"file": ("lifecycle.txt", b"Hello", "text/plain")}
    upload_res = await client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 202
    doc_id = upload_res.json()["id"]

    # 2. Check Status
    status_res = await client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["id"] == doc_id
    # Note: Status could be pending or processing depending on background task timing,
    # but it shouldn't be 404.

    # 3. Get Content (might be None if not done yet, but endpoint should exist)
    content_res = await client.get(f"/api/v1/documents/{doc_id}/content")
    assert content_res.status_code == 200
    assert content_res.json()["id"] == doc_id

    # 4. Delete
    delete_res = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_res.status_code == 204

    # 5. Verify Deleted
    status_res_after = await client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_res_after.status_code == 404


@pytest.mark.asyncio
async def test_missing_api_key() -> None:
    # Use a client without the API key header
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as unauth_client:
        files = {"file": ("test.txt", b"Hello", "text/plain")}
        response = await unauth_client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid or missing API key"
