import os
import uuid

import pytest

from app.vectorstore.qdrant_store import QdrantStore
from tests.fakes import FakeEmbeddingProvider

pytestmark = pytest.mark.integration

QDRANT_URL = os.environ.get("TEST_QDRANT_URL", "http://localhost:6333")
DIM = 16


@pytest.fixture
def real_qdrant():
    collection = f"itest_{uuid.uuid4().hex[:8]}"
    try:
        store = QdrantStore(
            url=QDRANT_URL,
            api_key=None,
            collection=collection,
            embedding_provider=FakeEmbeddingProvider(dim=DIM),
            embedding_dim=DIM,
            validate_dimension=False,  # the fake is deterministic by construction
        )
    except Exception as exc:
        pytest.skip(
            f"Qdrant not reachable at {QDRANT_URL} ({exc}) - run `docker compose up -d qdrant` "
            "to exercise the real-Qdrant integration tests"
        )
    if not store.ping():
        pytest.skip(f"Qdrant at {QDRANT_URL} did not respond to ping()")
    yield store
    store._client.delete_collection(collection)


def test_upsert_then_similarity_search_finds_the_document(real_qdrant):
    real_qdrant.upsert(
        ids=[str(uuid.uuid4())],
        texts=["Qdrant is a vector database used for similarity search."],
        metadatas=[{"source": "itest.md"}],
    )

    results = real_qdrant.similarity_search("Qdrant is a vector database", k=1)

    assert len(results) == 1
    assert "vector database" in results[0].text
    assert results[0].metadata.get("source") == "itest.md"


def test_similarity_search_on_empty_collection_returns_nothing(real_qdrant):
    assert real_qdrant.similarity_search("anything", k=3) == []


def test_upsert_multiple_documents_and_respect_k(real_qdrant):
    ids = [str(uuid.uuid4()) for _ in range(3)]
    texts = ["Document one.", "Document two.", "Document three."]
    real_qdrant.upsert(ids=ids, texts=texts, metadatas=[{}] * 3)

    results = real_qdrant.similarity_search("Document", k=2)

    assert len(results) == 2
