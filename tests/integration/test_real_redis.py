import os

import pytest

from app.cache.redis_store import RedisCacheStore

pytestmark = pytest.mark.integration

REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
def real_redis():
    store = RedisCacheStore(REDIS_URL)
    if not store.ping():
        pytest.skip(
            f"Redis not reachable at {REDIS_URL} - run `docker compose up -d redis` "
            "to exercise the real-Redis integration tests"
        )
    yield store
    # best-effort cleanup of this test's own keys
    store._client.flushdb()


def test_set_then_get_roundtrips_through_real_redis(real_redis):
    real_redis.set("itest:key", "hello")
    assert real_redis.get("itest:key") == "hello"


def test_get_missing_key_returns_none(real_redis):
    assert real_redis.get("itest:does-not-exist") is None


def test_incr_accumulates_and_get_sees_the_same_value(real_redis):
    real_redis.incr("itest:counter", amount=1, ttl=30)
    real_redis.incr("itest:counter", amount=4, ttl=30)
    assert real_redis.get("itest:counter") == "5"


def test_incr_ttl_is_only_applied_once(real_redis):
    # Second call must not reset the TTL to a huge value if the key
    # already existed - this guards the "value == amount" first-write check.
    real_redis.incr("itest:ttl-once", amount=1, ttl=5)
    real_redis.incr("itest:ttl-once", amount=1, ttl=99999)
    ttl = real_redis._client.ttl("itest:ttl-once")
    assert 0 < ttl <= 5
