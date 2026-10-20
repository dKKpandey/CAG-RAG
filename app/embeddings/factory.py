from app.core.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.embeddings.voyage_provider import VoyageEmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage")
        return VoyageEmbeddingProvider(api_key=settings.voyage_api_key, model=settings.voyage_model)

    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key, model=settings.openai_embedding_model
        )

    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
