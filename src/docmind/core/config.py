from pydantic_settings import BaseSettings, SettingsConfigDict

from docmind.chunking.strategy import ChunkingStrategy


class Settings(BaseSettings):
    project_name: str = "DocMind"
    api_v1_str: str = "/api/v1"
    environment: str = "development"

    # Database
    database_url: str = (
        "postgresql+asyncpg://docmind:docmind_dev_2026@localhost:5432/docmind_db"
    )

    # Auth
    api_key: str = "docmind-dev-key-2026"

    # Storage — where uploaded document bytes are saved on disk so the
    # background processing task can read them after the request ends.
    upload_dir: str = "uploads"

    # Chunking — "structural" is the production default (real document
    # boundaries when available); "fixed_size" and "semantic" exist for
    # comparison, see scripts/compare_chunking.py.
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.STRUCTURAL

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
