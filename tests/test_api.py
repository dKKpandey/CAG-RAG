from fastapi.testclient import TestClient

from app.api import deps
from app.api.deps import get_pipeline
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


def test_query_requires_api_key():
    client = TestClient(app)
    resp = client.post("/v1/query", json={"query": "hi"})
    assert resp.status_code == 401


def test_query_rejects_wrong_api_key():
    client = TestClient(app)
    resp = client.post("/v1/query", json={"query": "hi"}, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_query_returns_answer_with_valid_key():
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


def test_query_rejects_empty_query():
    app.dependency_overrides[get_pipeline] = lambda: _StubPipeline()
    try:
        client = TestClient(app)
        resp = client.post("/v1/query", json={"query": ""}, headers={"X-API-Key": "dev-local-key"})
        assert resp.status_code == 422
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
