import pytest

from app.core.config import Settings
from app.core.errors import RateLimitExceededError
from app.core.rate_limit import enforce_rate_limit


def _settings(**overrides) -> Settings:
    base = Settings(_env_file=None, api_key="test")
    return base.model_copy(update=overrides)


def test_disabled_when_limit_is_zero(fake_cache_store):
    settings = _settings(rate_limit_per_minute=0)
    for _ in range(100):
        enforce_rate_limit(fake_cache_store, settings, "alice")  # never raises


def test_allows_up_to_the_configured_limit(fake_cache_store):
    settings = _settings(rate_limit_per_minute=3)
    for _ in range(3):
        enforce_rate_limit(fake_cache_store, settings, "alice")  # never raises


def test_blocks_the_request_past_the_limit(fake_cache_store):
    settings = _settings(rate_limit_per_minute=3)
    for _ in range(3):
        enforce_rate_limit(fake_cache_store, settings, "alice")

    with pytest.raises(RateLimitExceededError):
        enforce_rate_limit(fake_cache_store, settings, "alice")


def test_limits_are_independent_per_client(fake_cache_store):
    settings = _settings(rate_limit_per_minute=1)
    enforce_rate_limit(fake_cache_store, settings, "alice")
    enforce_rate_limit(fake_cache_store, settings, "bob")  # bob's own budget, not alice's
