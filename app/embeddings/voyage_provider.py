
import voyageai

from app.core.retry import with_provider_retries
from app.embeddings.base import EmbeddingProvider


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Anthropic recommends Voyage AI for embeddings since Claude itself
    doesn't expose an embedding endpoint."""

    def __init__(self, api_key: str, model: str):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    @with_provider_retries
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self._model, input_type="document")
        return result.embeddings

    @with_provider_retries
    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed([text], model=self._model, input_type="query")
        return result.embeddings[0]
