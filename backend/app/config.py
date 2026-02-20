"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # AWS
    s3_bucket: str = "itsm-documents"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    chat_model: str = "llama3.2:3b"

    # ChromaDB
    chroma_persist_dir: str = "/app/chroma_data"
    chroma_collection_name: str = "itsm_docs"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Retrieval
    top_k_results: int = 5

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["*"]


settings = Settings()
