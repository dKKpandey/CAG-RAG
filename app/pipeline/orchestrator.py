import logging
from dataclasses import dataclass

from app.cache.base import CacheStore
from app.core.config import Settings
from app.llm.base import LLMProvider
from app.pipeline import cag, composer, rag
from app.schemas.models import QueryResponse, SourceChunk, UsageInfo
from app.vectorstore.base import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class CagRagPipeline:
    cache_store: CacheStore
    vector_store: VectorStore
    llm_provider: LLMProvider
    settings: Settings

    def answer(self, query: str, top_k: int | None = None) -> QueryResponse:
        cached_context = cag.get_cached_context(
            self.cache_store, self.settings.cache_key_prefix, self.settings.cache_key_version
        )
        chunks = rag.retrieve_live_context(self.vector_store, query, top_k or self.settings.top_k)
        retrieved_text = rag.format_retrieved(chunks)

        messages = composer.compose_messages(cached_context, retrieved_text, query)
        result = self.llm_provider.generate(messages)

        logger.info("Answered query (cache_hit=%s, sources=%d)", result.cache_hit, len(chunks))
        return QueryResponse(
            answer=result.text,
            sources=[
                SourceChunk(id=c.id, text=c.text, score=c.score, metadata=c.metadata)
                for c in chunks
            ],
            cache_hit=result.cache_hit,
            usage=UsageInfo(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_read_input_tokens=result.usage.cache_read_input_tokens,
                cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
            ),
        )
