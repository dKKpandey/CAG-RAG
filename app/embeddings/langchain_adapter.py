
from langchain_core.embeddings import Embeddings

from app.embeddings.base import EmbeddingProvider


class LangChainEmbeddingsAdapter(Embeddings):
    """Wraps our provider-agnostic EmbeddingProvider so it can be handed to
    any LangChain VectorStore, which expects its own Embeddings ABC."""

    def __init__(self, provider: EmbeddingProvider):
        self._provider = provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._provider.embed_query(text)
