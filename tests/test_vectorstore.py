from app.pipeline import rag


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
