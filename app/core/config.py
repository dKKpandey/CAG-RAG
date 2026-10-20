from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- service ---
    app_name: str = "cag-rag-service"
    environment: Literal["development", "production", "test"] = "development"
    api_key: str = Field(default="dev-local-key", description="Required in the X-API-Key header")
    log_level: str = "INFO"

    # --- LLM (generation) ---
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # --- Embeddings ---
    embedding_provider: Literal["voyage", "openai"] = "voyage"
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3"
    openai_embedding_model: str = "text-embedding-3-small"
    # Must match the output dimension of whichever embedding model is active.
    embedding_dim: int = 1024

    # --- Cache store (CAG) ---
    redis_url: str = "redis://localhost:6379/0"
    cache_key_prefix: str = "cag:cached_context"
    cache_key_version: str = "v1"
    cold_source_dir: str = "data/cold_sources"
    cached_context_max_tokens: int = 6000

    # --- Vector store (RAG) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "rag_documents"
    top_k: int = 4

    # --- chunking (hot ingestion) ---
    chunk_size: int = 800
    chunk_overlap: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
