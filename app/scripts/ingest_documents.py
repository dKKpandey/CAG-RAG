import argparse

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.embeddings.factory import build_embedding_provider
from app.ingestion.loaders import load_and_chunk_texts, load_directory
from app.vectorstore.qdrant_store import QdrantStore


def main() -> None:
    configure_logging()
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Batch-ingest hot/live documents into the RAG vector store."
    )
    parser.add_argument("--source", default="data/hot_sources")
    args = parser.parse_args()

    embedding_provider = build_embedding_provider(settings)
    store = QdrantStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
        embedding_provider=embedding_provider,
        embedding_dim=settings.embedding_dim,
    )

    texts = load_directory(args.source)
    ids, chunks, metadatas = load_and_chunk_texts(
        texts, settings.chunk_size, settings.chunk_overlap
    )
    store.upsert(ids, chunks, metadatas)
    print(
        f"Ingested {len(chunks)} chunk(s) from {len(texts)} file(s) "
        f"into '{settings.qdrant_collection}'."
    )


if __name__ == "__main__":
    main()
