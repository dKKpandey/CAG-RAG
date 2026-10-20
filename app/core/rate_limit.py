import time

from app.cache.base import CacheStore
from app.core.config import Settings
from app.core.errors import RateLimitExceededError

_WINDOW_SECONDS = 60
_KEY_TTL = 120  # outlives one window so a slightly-late request still counts correctly


def enforce_rate_limit(cache_store: CacheStore, settings: Settings, client_id: str) -> None:
    """Fixed-window counter in the cache store: RATE_LIMIT_PER_MINUTE
    requests per client_id per 60-second window. Simple and good enough for
    a reference service; a sliding window or token bucket would smooth
    bursts at window boundaries better, at the cost of more Redis calls."""

    if settings.rate_limit_per_minute <= 0:
        return

    window = int(time.time() // _WINDOW_SECONDS)
    key = f"ratelimit:{client_id}:{window}"
    count = cache_store.incr(key, amount=1, ttl=_KEY_TTL)
    if count > settings.rate_limit_per_minute:
        raise RateLimitExceededError(
            f"Rate limit exceeded: {settings.rate_limit_per_minute} requests/minute "
            "for this API key"
        )
