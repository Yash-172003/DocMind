import pytest
from httpx import ASGITransport, AsyncClient

from docmind.main import app, lifespan


@pytest.mark.asyncio
async def test_health_check() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_lifespan_creates_tables_and_disposes_engine_cleanly() -> None:
    # ASGITransport doesn't trigger ASGI lifespan events by default, so
    # this is the only test that runs main.py's startup/shutdown at all.
    # create_all is idempotent — safe to run again against the real dev DB.
    async with lifespan(app):
        pass
