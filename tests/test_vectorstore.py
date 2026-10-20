import pytest

from app.core.errors import ConfigurationError
from app.pipeline import rag
from app.vectorstore.qdrant_store import validate_embedding_dimension
from tests.fakes import FakeEmbeddingProvider


def test_validate_embedding_dimension_passes_when_matching():
    validate_embedding_dimension(FakeEmbeddingProvider(dim=16), expected_dim=16)


def test_validate_embedding_dimension_raises_clear_error_when_mismatched():
    with pytest.raises(ConfigurationError, match="EMBEDDING_DIM is set to 999"):
        validate_embedding_dimension(FakeEmbeddingProvider(dim=16), expected_dim=999)


def test_retrieve_and_format(fake_vector_store):
    chunks = rag.retrieve_live_context(fake_vector_store, "what is qdrant", k=3)

    assert len(chunks) == 1
    assert chunks[0].text.startswith("Qdrant")

    text = rag.format_retrieved(chunks)
    assert "doc-1" in text
    assert "Qdrant" in text


def test_retrieve_respects_k(fake_vector_store):
    chunks = rag.retrieve_live_context(fake_vector_store, "anything", k=0)
    assert chunks == []


def test_format_retrieved_empty():
    assert "no relevant" in rag.format_retrieved([]).lower()
