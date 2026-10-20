
from app.vectorstore.base import RetrievedChunk, VectorStore


def retrieve_live_context(vector_store: VectorStore, query: str, k: int) -> list[RetrievedChunk]:
    """Steps 3-4 of RAG: embed the query (inside the vector store call) and
    run a similarity search against whatever hot sources have been ingested."""

    return vector_store.similarity_search(query, k=k)


def format_retrieved(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant live documents were found for this query)"

    parts = [f"[{c.id}] (score={c.score:.3f})\n{c.text}" for c in chunks]
    return "\n\n".join(parts)
