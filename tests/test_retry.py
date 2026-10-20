import pytest

from app.core.retry import with_provider_retries


def test_retries_until_success():
    calls = {"count": 0}

    @with_provider_retries
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ConnectionError("simulated transient failure")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3


def test_reraises_the_original_exception_after_exhausting_attempts():
    calls = {"count": 0}

    @with_provider_retries
    def always_fails():
        calls["count"] += 1
        raise ConnectionError("simulated permanent failure")

    with pytest.raises(ConnectionError, match="simulated permanent failure"):
        always_fails()
    assert calls["count"] == 3  # stop_after_attempt(3)
