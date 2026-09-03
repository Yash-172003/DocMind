"""DocMind FastAPI application entry point.

Architectural decisions:
- Lifespan context manager: runs code on startup (create DB tables) and
  shutdown (dispose engine). Replaces the deprecated @app.on_event pattern.
- Global exception handler: catches unhandled errors and returns a clean
  JSON response instead of a raw 500 traceback.
- Router mounting: all document endpoints live under /api/v1/documents,
  making API versioning trivial when we eventually need v2.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from docmind.api.v1.endpoints.documents import router as documents_router
from docmind.api.v1.endpoints.search import router as search_router
from docmind.core.config import settings
from docmind.core.logging import configure_logging
from docmind.db.base import engine
from docmind.db.models import Base

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown logic for the application.

    Startup: create all database tables if they don't exist.
    Shutdown: cleanly dispose the database engine.

    Note: In production, we would use Alembic migrations instead of
    create_all(). But for development, this ensures the tables exist
    without running a separate migration command every time.
    """
    logger.info("application_starting", project=settings.project_name)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_ready")
    yield
    await engine.dispose()
    logger.info("application_shutdown")


app = FastAPI(
    title="DocMind API",
    description="Enterprise Document Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(documents_router, prefix=settings.api_v1_str)
app.include_router(search_router, prefix=settings.api_v1_str)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch any unhandled exception and return a clean JSON error.

    Without this, FastAPI would return raw tracebacks to the client,
    which is both a security risk and bad UX.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint — no auth required."""
    logger.info("health_check_requested", status="healthy")
    return {"status": "healthy"}
