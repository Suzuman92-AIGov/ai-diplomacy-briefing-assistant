from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Diplomacy Briefing Assistant"
    app_env: str = "local"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aidiplomacy"

    # Retrieval mode: "local" for TF-IDF demo mode, "openai" for embeddings + pgvector.
    embedding_provider: str = "local"

    # Answer mode: "local" for extractive answers, "openai" for LLM-generated answers.
    answer_provider: str = "local"

    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4.1-mini"

    default_top_k: int = 6
    event_near_duplicate_title_threshold: float = 0.92
    event_semantic_similarity_threshold: float = 0.78
    event_title_match_window_days: int = 14
    ingestion_request_timeout_seconds: int = 30
    ingestion_max_download_bytes: int = 25 * 1024 * 1024
    ingestion_max_extracted_text_chars: int = 2_000_000
    ingestion_error_max_chars: int = 240

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
