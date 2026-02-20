"""Environment & defaults configuration."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "phi3:medium"
    ollama_embed_model: str = "nomic-embed-text"

    # OpenSearch (optional)
    opensearch_enabled: bool = False
    opensearch_url: str = "http://localhost:9200"
    opensearch_index: str = "cnap-events"

    # SQLite
    sqlite_dir: str = "/app/data"

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Rate limiting
    rate_limit_per_minute: int = 60


@lru_cache()
def get_settings() -> Settings:
    return Settings()
