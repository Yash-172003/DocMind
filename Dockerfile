# syntax=docker/dockerfile:1

# ---- Base: shared foundation for both dev and production images ----
FROM python:3.12-slim AS base

# uv ships as a static binary — copying it from its own image is faster
# and more reliable than installing it via pip.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

WORKDIR /app

# Copy only the dependency manifest first. Docker caches layers by their
# inputs — as long as pyproject.toml/uv.lock don't change, this layer
# (and the slow `uv sync` step) is reused even when app code changes.
COPY pyproject.toml uv.lock ./

# ---- Development target ----
# Includes dev dependencies (pytest, ruff, mypy) and runs with --reload.
# docker-compose mounts ./src over /app/src so edits show up without a rebuild.
FROM base AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "docmind.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- Production target ----
# No dev dependencies, no reload, runs as a non-root user.
# App code is copied in after dependency install so code-only changes
# don't invalidate the dependency layer.
FROM base AS production

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "docmind.main:app", "--host", "0.0.0.0", "--port", "8000"]
