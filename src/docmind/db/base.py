"""Async SQLAlchemy engine and session factory.

Architectural decision: We use AsyncSession with asyncpg as the driver.
This means every database call is non-blocking — FastAPI can serve other
requests while waiting for PostgreSQL to respond. This is critical for
a document processing API where DB queries happen on every request.

Alternative considered: synchronous SQLAlchemy with psycopg2.
Tradeoff: simpler code but blocks the event loop. Unacceptable for
a production async API.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docmind.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    # --- Connection Pooling Configuration ---
    # Without pooling, every API request would open a brand new TCP connection
    # to PostgreSQL (~50ms handshake), use it, then throw it away. With pooling,
    # we keep a set of connections alive and reuse them.
    pool_size=5,  # Keep 5 persistent connections in the pool
    max_overflow=10,  # Allow up to 10 extra connections under load (total max: 15)
    pool_timeout=30,  # If all 15 are busy, wait 30s before raising an error
    pool_pre_ping=True,  # Check if a connection is still alive before using it
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, auto-closing when the request ends."""
    async with async_session_factory() as session:
        yield session
