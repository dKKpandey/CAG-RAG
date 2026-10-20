
import redis

from app.cache.base import CacheStore


class RedisCacheStore(CacheStore):
    """Durable store for the assembled CAG cached-context block, so a service
    restart doesn't require re-reading, re-chunking and re-encoding the cold
    sources. This is distinct from — and sits below — the LLM provider's own
    inference-time prompt cache (see app/llm/anthropic_provider.py)."""

    def __init__(self, url: str):
        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._client.set(key, value, ex=ttl)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False
