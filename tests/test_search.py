"""End-to-end: upload a real document through the API, then search it
through the API — proves the search endpoint is wired correctly to the
real pipeline, not just that the underlying retrieval functions work
(already covered in tests/retrieval/).
"""

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
async def test_search_finds_uploaded_document_content(client: AsyncClient) -> None:
    text = "The zylophant sanctuary opened its gates for the first time today."
    files = {"file": ("sanctuary.txt", text.encode(), "text/plain")}
    upload_res = await client.post("/api/v1/documents/upload", files=files)
    doc_id = upload_res.json()["id"]
    await client.get(f"/api/v1/documents/{doc_id}/content")  # wait for processing

    search_res = await client.get(
        "/api/v1/search", params={"q": "zylophant", "document_id": doc_id}
    )
    results = search_res.json()

    assert search_res.status_code == 200
    assert len(results) >= 1
    assert "zylophant" in results[0]["text"].lower()

    await client.delete(f"/api/v1/documents/{doc_id}")


@pytest.mark.asyncio
async def test_search_without_rerank_still_works(client: AsyncClient) -> None:
    text = "Quixotical events happen rarely in the archive."
    files = {"file": ("archive.txt", text.encode(), "text/plain")}
    upload_res = await client.post("/api/v1/documents/upload", files=files)
    doc_id = upload_res.json()["id"]
    await client.get(f"/api/v1/documents/{doc_id}/content")

    search_res = await client.get(
        "/api/v1/search",
        params={"q": "quixotical", "document_id": doc_id, "rerank": "false"},
    )
    results = search_res.json()

    assert search_res.status_code == 200
    assert len(results) >= 1

    await client.delete(f"/api/v1/documents/{doc_id}")


@pytest.mark.asyncio
async def test_search_requires_api_key() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as unauth_client:
        response = await unauth_client.get("/api/v1/search", params={"q": "anything"})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/search", params={"q": ""})
    assert response.status_code == 422
