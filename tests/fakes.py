
from app.cache.base import CacheStore
from app.llm.base import ChatMessage, LLMProvider, LLMResponse, LLMUsage
from app.vectorstore.base import RetrievedChunk, VectorStore


class FakeCacheStore(CacheStore):
    def __init__(self):
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._data[key] = value

    def ping(self) -> bool:
        return True


class FakeVectorStore(VectorStore):
    def __init__(self, chunks: list[RetrievedChunk] | None = None):
        self._chunks: list[RetrievedChunk] = list(chunks or [])

    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
        for i, t, m in zip(ids, texts, metadatas):
            self._chunks.append(RetrievedChunk(id=i, text=t, score=1.0, metadata=m))

    def similarity_search(self, query: str, k: int) -> list[RetrievedChunk]:
        return self._chunks[:k]

    def ping(self) -> bool:
        return True


class FakeLLMProvider(LLMProvider):
    def __init__(self, canned_answer: str = "This is a canned answer."):
        self.canned_answer = canned_answer
        self.last_messages: list[ChatMessage] | None = None

    def generate(self, messages, *, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        self.last_messages = messages
        return LLMResponse(
            text=self.canned_answer,
            usage=LLMUsage(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
            cache_hit=False,
        )
