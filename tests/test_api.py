import json

from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import get_pipeline
from app.core.config import Settings
from app.main import app
from app.schemas.models import QueryResponse, SourceChunk, UsageInfo
from tests.fakes import FakeCacheStore, FakeVectorStore


class _StubPipeline:
    def answer(self, query: str, top_k=None) -> QueryResponse:
        return QueryResponse(
            answer="stub answer",
            sources=[SourceChunk(id="doc-1", text="...", score=0.9, metadata={})],
            cache_hit=True,
            usage=UsageInfo(input_tokens=1, output_tokens=1),
        )

    def answer_stream(self, query: str, top_k=None):
        yield {"type": "sources", "sources": []}
        for word in ["hello", "world"]:
            yield {"type": "token", "token": word}
        yield {"type": "done"}


def _settings(**overrides) -> Settings:
    base = Settings(_env_file=None, api_key="dev-local-key")
    return base.model_copy(update=overrides)


def _patch_auth(monkeypatch, cache_store=None, settings=None):
    """Two different seams need two different techniques here:

    - routes_query.query() declares `cache_store: CacheStore =
      Depends(get_cache_store)` — FastAPI captured that exact function
      object when the route was registered (at app import time), so
      overriding it needs `app.dependency_overrides`, keyed by that same
      object. That override must be registered *before* the module
      attribute is patched below, while `deps.get_cache_store` still *is*
      that original object.
    - get_authenticated_client() calls get_cache_store()/get_settings() as
      plain functions in its own body, not as Depends() parameters, so
      dependency_overrides can't reach them — only monkeypatching the
      module attribute (a real global-name rebind, resolved at call time)
      does.
    """

    store = cache_store or FakeCacheStore()
    app.dependency_overrides[deps.get_cache_store] = lambda: store
    monkeypatch.setattr(deps, "get_cache_store", lambda: store)
    if settings is not None:
        monkeypatch.setattr(deps, "get_settings", lambda: settings)
        monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    return store


def test_query_requires_api_key():
    client = TestClient(app)
    resp = client.post("/v1/query", json={"query": "hi"})
    assert resp.status_code == 401


def test_query_rejects_wrong_api_key(monkeypatch):
    _patch_auth(monkeypatch)
    client = TestClient(app)
    resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_query_returns_answer_with_valid_key(monkeypatch):
    _patch_auth(monkeypatch)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": "dev-local-key"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "stub answer"
        assert body["cache_hit"] is True
    finally:
        app.dependency_overrides.clear()


def test_query_rejects_empty_query(monkeypatch):
    _patch_auth(monkeypatch)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        resp = client.post("/v1/query", json={"query": ""}, headers={"X-API-Key": "dev-local-key"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_query_stream_returns_sse_events(monkeypatch):
    _patch_auth(monkeypatch)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        with client.stream(
            "POST",
            "/v1/query/stream",
            json={"query": "hi"},
            headers={"X-API-Key": "dev-local-key"},
        ) as resp:
            assert resp.status_code == 200
            events = [
                json.loads(line[len("data: ") :])
                for line in resp.iter_lines()
                if line.startswith("data: ")
            ]
    finally:
        app.dependency_overrides.clear()

    assert events[0] == {"type": "sources", "sources": []}
    assert events[1] == {"type": "token", "token": "hello"}
    assert events[2] == {"type": "token", "token": "world"}
    assert events[-1] == {"type": "done"}


def test_multiple_api_keys_resolve_to_different_clients(monkeypatch):
    settings = _settings(api_keys="key-a:alice,key-b:bob", rate_limit_per_minute=0)
    _patch_auth(monkeypatch, settings=settings)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        for key in ("key-a", "key-b", "dev-local-key"):
            resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": key})
            assert resp.status_code == 200, key
        resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": "unknown"})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_rate_limit_blocks_after_the_configured_number_of_requests(monkeypatch):
    settings = _settings(rate_limit_per_minute=2)
    cache_store = FakeCacheStore()
    _patch_auth(monkeypatch, cache_store=cache_store, settings=settings)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        headers = {"X-API-Key": "dev-local-key"}
        assert client.post("/v1/query", json={"query": "1"}, headers=headers).status_code == 200
        assert client.post("/v1/query", json={"query": "2"}, headers=headers).status_code == 200
        third = client.post("/v1/query", json={"query": "3"}, headers=headers)
        assert third.status_code == 429
    finally:
        app.dependency_overrides.clear()


def test_daily_budget_blocks_once_exceeded(monkeypatch):
    settings = _settings(rate_limit_per_minute=0, max_daily_tokens_per_client=5)
    cache_store = FakeCacheStore()
    # Pre-seed today's usage over the cap, as if earlier requests already spent it.
    from app.core.budget import _budget_key

    cache_store.set(_budget_key("default"), "10")
    _patch_auth(monkeypatch, cache_store=cache_store, settings=settings)
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": "dev-local-key"})
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint_reports_dependency_status(monkeypatch):
    monkeypatch.setattr(deps, "get_cache_store", lambda: FakeCacheStore())
    monkeypatch.setattr(deps, "get_vector_store", lambda: FakeVectorStore())

    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["redis_ok"] is True
    assert body["vector_store_ok"] is True


def test_health_endpoint_reports_false_instead_of_crashing_when_unconfigured(monkeypatch):
    def _raise():
        raise RuntimeError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage")

    monkeypatch.setattr(deps, "get_cache_store", _raise)
    monkeypatch.setattr(deps, "get_vector_store", _raise)

    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["redis_ok"] is False
    assert body["vector_store_ok"] is False
