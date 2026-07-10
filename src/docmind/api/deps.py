"""Dependency injection providers for FastAPI.

Architectural decision: FastAPI's Depends() system is its most powerful
pattern. Instead of importing database sessions or checking auth in
every endpoint function, we declare dependencies once and FastAPI
automatically injects them. This keeps endpoints clean and testable.
"""

from collections.abc import AsyncGenerator

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from docmind.core.config import settings
from docmind.db.base import get_async_session

# API Key security scheme — tells Swagger UI to show a key input
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the duration of one request.

    This is a thin wrapper so endpoints depend on this function,
    making it easy to swap in a test database later.
    """
    async for session in get_async_session():
        yield session


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Validate the X-API-Key header against our configured key.

    Returns the key if valid, raises 403 if not.

    Architectural note: This is simple API key auth, not OAuth2 or JWT.
    For an internal enterprise tool, this is appropriate. We would
    upgrade to JWT when we add user-level permissions in a later phase.
    """
    if api_key is None or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return api_key
