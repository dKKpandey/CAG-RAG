import pytest

from app.vectorstore.base import RetrievedChunk
from tests.fakes import FakeCacheStore, FakeLLMProvider, FakeVectorStore


@pytest.fixture
def fake_cache_store():
    return FakeCacheStore()


@pytest.fixture
def fake_vector_store():
    return FakeVectorStore(
        [RetrievedChunk(id="doc-1", text="Qdrant is a vector database.", score=0.92, metadata={"source": "faq.md"})]
    )


@pytest.fixture
def fake_llm_provider():
    return FakeLLMProvider()
