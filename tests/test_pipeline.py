from app.core.config import Settings
from app.pipeline.orchestrator import CagRagPipeline


def _settings() -> Settings:
    return Settings(_env_file=None, api_key="test")


def test_pipeline_combines_cached_and_retrieved_context(fake_cache_store, fake_vector_store, fake_llm_provider):
    fake_cache_store.set(
        "cag:cached_context:v1",
        '{"text": "Acme PTO policy: 20 days per year.", "hash": "x", "files": []}',
    )
    pipeline = CagRagPipeline(fake_cache_store, fake_vector_store, fake_llm_provider, _settings())

    response = pipeline.answer("How many PTO days do I get?")

    assert response.answer == fake_llm_provider.canned_answer
    assert response.sources[0].id == "doc-1"

    sent_text = " ".join(block.text for message in fake_llm_provider.last_messages for block in message.blocks)
    assert "Acme PTO policy" in sent_text
    assert "Qdrant is a vector database" in sent_text
    assert "How many PTO days do I get?" in sent_text


def test_pipeline_marks_cached_block_as_cacheable(fake_cache_store, fake_vector_store, fake_llm_provider):
    fake_cache_store.set(
        "cag:cached_context:v1", '{"text": "Stable fact.", "hash": "x", "files": []}'
    )
    pipeline = CagRagPipeline(fake_cache_store, fake_vector_store, fake_llm_provider, _settings())

    pipeline.answer("Any question")

    user_message = next(m for m in fake_llm_provider.last_messages if m.role == "user")
    cacheable_blocks = [b for b in user_message.blocks if b.cacheable]
    non_cacheable_blocks = [b for b in user_message.blocks if not b.cacheable]

    assert len(cacheable_blocks) == 1
    assert "Stable fact." in cacheable_blocks[0].text
    assert len(non_cacheable_blocks) == 1
    assert "Any question" in non_cacheable_blocks[0].text


def test_pipeline_raises_when_cache_not_preloaded(fake_cache_store, fake_vector_store, fake_llm_provider):
    from app.core.errors import CacheNotPreloadedError

    pipeline = CagRagPipeline(fake_cache_store, fake_vector_store, fake_llm_provider, _settings())

    import pytest

    with pytest.raises(CacheNotPreloadedError):
        pipeline.answer("Anything")
