import pytest

from app.core.errors import CacheNotPreloadedError
from app.pipeline import cag


def test_get_cached_context_raises_when_missing(fake_cache_store):
    with pytest.raises(CacheNotPreloadedError):
        cag.get_cached_context(fake_cache_store, "cag:cached_context", "v1")


def test_preload_and_get_roundtrip(fake_cache_store, tmp_path):
    (tmp_path / "handbook.md").write_text("# Handbook\nBe kind.", encoding="utf-8")

    cag.preload_cold_sources(fake_cache_store, str(tmp_path), "cag:cached_context", "v1", max_chars=10_000)
    text = cag.get_cached_context(fake_cache_store, "cag:cached_context", "v1")

    assert "Be kind." in text


def test_preload_raises_when_no_sources(fake_cache_store, tmp_path):
    with pytest.raises(FileNotFoundError):
        cag.preload_cold_sources(fake_cache_store, str(tmp_path), "cag:cached_context", "v1", max_chars=10_000)


def test_preload_truncates_to_max_chars(fake_cache_store, tmp_path):
    (tmp_path / "big.md").write_text("x" * 1000, encoding="utf-8")

    payload = cag.preload_cold_sources(fake_cache_store, str(tmp_path), "cag:cached_context", "v1", max_chars=50)

    assert len(payload["text"]) == 50


def test_incr_starts_at_amount_and_accumulates(fake_cache_store):
    assert fake_cache_store.incr("counter", amount=3) == 3
    assert fake_cache_store.incr("counter", amount=4) == 7
    assert fake_cache_store.get("counter") == "7"


def test_incr_default_amount_is_one(fake_cache_store):
    fake_cache_store.incr("hits")
    fake_cache_store.incr("hits")
    assert fake_cache_store.get("hits") == "2"
