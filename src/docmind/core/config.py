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

    # Embeddings — BAAI/bge-large-en-v1.5 is the production default: it
    # runs locally (free, keeps documents private) and produces 1024-dim
    # vectors matching the chunks.embedding column from Week 5-6. See
    # docmind.embedding.embedder for why this model over alternatives.
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_batch_size: int = 32

    # Retrieval — cross-encoder for the final reranking pass over hybrid
    # search's fused candidates. See docmind.retrieval.reranker for why
    # this differs from the bi-encoder embedding model above.
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
