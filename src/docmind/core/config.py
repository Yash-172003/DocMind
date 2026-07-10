from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
