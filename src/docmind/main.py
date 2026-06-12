from fastapi import FastAPI

app = FastAPI(
    title="DocMind API",
    description="Enterprise Document Intelligence Platform",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
