import logging
from collections.abc import Iterator
from dataclasses import dataclass

from app.cache.base import CacheStore
from app.core.config import Settings
from app.llm.base import ChatMessage, LLMProvider
from app.pipeline import cag, composer, rag
from app.schemas.models import QueryResponse, SourceChunk, UsageInfo
from app.vectorstore.base import RetrievedChunk, VectorStore

logger = logging.getLogger(__name__)


@dataclass
class CagRagPipeline:
    cache_store: CacheStore
    vector_store: VectorStore
    llm_provider: LLMProvider
    settings: Settings

    def _prepare(
        self, query: str, top_k: int | None
    ) -> tuple[list[ChatMessage], list[RetrievedChunk]]:
        """Steps 1-5, shared by answer() and answer_stream(): cache lookup,
        live retrieval, and prompt composition. Everything up to here is
        identical whether the caller wants a streamed or a complete answer —
        only step 6 (generation) differs."""

        cached_context = cag.get_cached_context(
            self.cache_store, self.settings.cache_key_prefix, self.settings.cache_key_version
        )
        chunks = rag.retrieve_live_context(self.vector_store, query, top_k or self.settings.top_k)
        retrieved_text = rag.format_retrieved(chunks)
        messages = composer.compose_messages(cached_context, retrieved_text, query)
        return messages, chunks

    @staticmethod
    def _to_source_chunks(chunks: list[RetrievedChunk]) -> list[SourceChunk]:
        return [
            SourceChunk(id=c.id, text=c.text, score=c.score, metadata=c.metadata) for c in chunks
        ]

    def answer(self, query: str, top_k: int | None = None) -> QueryResponse:
        messages, chunks = self._prepare(query, top_k)
        result = self.llm_provider.generate(messages)

        logger.info("Answered query (cache_hit=%s, sources=%d)", result.cache_hit, len(chunks))
        return QueryResponse(
            answer=result.text,
            sources=self._to_source_chunks(chunks),
            cache_hit=result.cache_hit,
            usage=UsageInfo(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_read_input_tokens=result.usage.cache_read_input_tokens,
                cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
            ),
        )

    def answer_stream(self, query: str, top_k: int | None = None) -> Iterator[dict]:
        """Yields a sequence of small dicts, newest-information-first: the
        sources (known as soon as retrieval finishes, before generation even
        starts), then each token as it's generated, then a final marker.
        No usage/cache_hit info is available mid-stream — providers only
        report it once the full response completes."""

        messages, chunks = self._prepare(query, top_k)
        sources = [c.model_dump() for c in self._to_source_chunks(chunks)]
        yield {"type": "sources", "sources": sources}
        for token in self.llm_provider.stream(messages):
            yield {"type": "token", "token": token}
        yield {"type": "done"}
