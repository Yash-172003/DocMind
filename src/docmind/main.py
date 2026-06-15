import structlog
from fastapi import FastAPI

from docmind.core.logging import configure_logging

# Initialize logging before app starts
configure_logging()
logger = structlog.get_logger()

app = FastAPI(
    title="DocMind API",
    description="Enterprise Document Intelligence Platform",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("health_check_requested", status="healthy")
    return {"status": "healthy"}
