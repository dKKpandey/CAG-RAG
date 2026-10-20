
from langchain_openai import OpenAIEmbeddings

from app.core.retry import with_provider_retries
from app.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        self._client = OpenAIEmbeddings(model=model, api_key=api_key)

    @with_provider_retries
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed_documents(texts)

    @with_provider_retries
    def embed_query(self, text: str) -> list[float]:
        return self._client.embed_query(text)
