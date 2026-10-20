from functools import lru_cache

from fastapi import Depends

from app.cache.base import CacheStore
from app.cache.redis_store import RedisCacheStore
from app.core.budget import check_budget
from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import ClientContext, require_api_key
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import build_embedding_provider
from app.llm.base import LLMProvider
from app.llm.factory import build_llm_provider
from app.pipeline.orchestrator import CagRagPipeline
from app.vectorstore.base import VectorStore
from app.vectorstore.qdrant_store import QdrantStore


@lru_cache
def get_cache_store() -> CacheStore:
    settings = get_settings()
    return RedisCacheStore(settings.redis_url)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())


@lru_cache
def get_vector_store() -> VectorStore:
    settings = get_settings()
    return QdrantStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
        embedding_provider=get_embedding_provider(),
        embedding_dim=settings.embedding_dim,
        validate_dimension=settings.validate_embedding_dim,
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())


def get_pipeline() -> CagRagPipeline:
    return CagRagPipeline(
        cache_store=get_cache_store(),
        vector_store=get_vector_store(),
        llm_provider=get_llm_provider(),
        settings=get_settings(),
    )


def get_authenticated_client(client: ClientContext = Depends(require_api_key)) -> ClientContext:
    """Auth, then rate limit, then budget — in that order, so an unknown
    key never consumes a rate-limit slot, and a rate-limited caller never
    reaches the (more expensive) budget check."""

    settings = get_settings()
    cache_store = get_cache_store()
    enforce_rate_limit(cache_store, settings, client.client_id)
    check_budget(cache_store, settings, client.client_id)
    return client
