from functools import lru_cache

from app.cache.base import CacheStore
from app.cache.redis_store import RedisCacheStore
from app.core.config import get_settings
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
