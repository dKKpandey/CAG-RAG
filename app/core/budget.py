from datetime import date

from app.cache.base import CacheStore
from app.core.config import Settings
from app.core.errors import BudgetExceededError

_TTL_SECONDS = 2 * 24 * 60 * 60  # outlive the day it tracks, for easy debugging


def _budget_key(client_id: str) -> str:
    return f"budget:{client_id}:{date.today().isoformat()}"


def get_usage_today(cache_store: CacheStore, client_id: str) -> int:
    raw = cache_store.get(_budget_key(client_id))
    return int(raw) if raw else 0


def check_budget(cache_store: CacheStore, settings: Settings, client_id: str) -> None:
    """Pre-check against *already recorded* usage from earlier today. This
    cannot know the cost of the request about to be made — that's
    unavoidable, since token count isn't known until after generation — so
    it bounds cumulative daily spend one request late at worst, not
    unboundedly."""

    if settings.max_daily_tokens_per_client <= 0:
        return
    if get_usage_today(cache_store, client_id) >= settings.max_daily_tokens_per_client:
        raise BudgetExceededError(
            f"Daily token budget ({settings.max_daily_tokens_per_client}) exceeded for this API key"
        )


def record_usage(cache_store: CacheStore, client_id: str, tokens: int) -> None:
    if tokens > 0:
        cache_store.incr(_budget_key(client_id), amount=tokens, ttl=_TTL_SECONDS)
