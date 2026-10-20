import pytest

from app.core.budget import check_budget, get_usage_today, record_usage
from app.core.config import Settings
from app.core.errors import BudgetExceededError


def _settings(**overrides) -> Settings:
    base = Settings(_env_file=None, api_key="test")
    return base.model_copy(update=overrides)


def test_disabled_when_cap_is_zero(fake_cache_store):
    settings = _settings(max_daily_tokens_per_client=0)
    record_usage(fake_cache_store, "alice", 10_000)
    check_budget(fake_cache_store, settings, "alice")  # never raises


def test_usage_accumulates_across_calls(fake_cache_store):
    record_usage(fake_cache_store, "alice", 100)
    record_usage(fake_cache_store, "alice", 50)
    assert get_usage_today(fake_cache_store, "alice") == 150


def test_zero_or_negative_usage_is_not_recorded(fake_cache_store):
    record_usage(fake_cache_store, "alice", 0)
    record_usage(fake_cache_store, "alice", -5)
    assert get_usage_today(fake_cache_store, "alice") == 0


def test_check_budget_blocks_once_usage_reaches_the_cap(fake_cache_store):
    settings = _settings(max_daily_tokens_per_client=100)
    record_usage(fake_cache_store, "alice", 100)

    with pytest.raises(BudgetExceededError):
        check_budget(fake_cache_store, settings, "alice")


def test_check_budget_allows_usage_under_the_cap(fake_cache_store):
    settings = _settings(max_daily_tokens_per_client=100)
    record_usage(fake_cache_store, "alice", 99)
    check_budget(fake_cache_store, settings, "alice")  # never raises


def test_budgets_are_independent_per_client(fake_cache_store):
    settings = _settings(max_daily_tokens_per_client=100)
    record_usage(fake_cache_store, "alice", 100)
    check_budget(fake_cache_store, settings, "bob")  # bob hasn't spent anything
