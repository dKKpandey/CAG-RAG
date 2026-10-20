
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore as LCQdrant
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.core.errors import ConfigurationError
from app.embeddings.base import EmbeddingProvider
from app.embeddings.langchain_adapter import LangChainEmbeddingsAdapter
from app.vectorstore.base import RetrievedChunk, VectorStore


def validate_embedding_dimension(embedding_provider: EmbeddingProvider, expected_dim: int) -> None:
    """Fail fast and clearly instead of letting Qdrant reject every insert
    later with a terser dimension-mismatch error. Costs one real embedding
    call. A standalone function (rather than a method) so it's unit-testable
    without a live Qdrant connection — see tests/test_vectorstore.py."""

    actual_dim = len(embedding_provider.embed_query("dimension probe"))
    if actual_dim != expected_dim:
        raise ConfigurationError(
            f"EMBEDDING_DIM is set to {expected_dim}, but the configured "
            f"embedding model actually returns {actual_dim}-dimensional "
            f"vectors. Update EMBEDDING_DIM in your .env to match, or set "
            f"VALIDATE_EMBEDDING_DIM=false to skip this check."
        )


class QdrantStore(VectorStore):
    """The hot/live side of RAG: whatever is upserted here is searched fresh
    on every query, in contrast to the CAG cache which is assembled once."""

    def __init__(
        self,
        url: str,
        api_key: str | None,
        collection: str,
        embedding_provider: EmbeddingProvider,
        embedding_dim: int,
        validate_dimension: bool = True,
    ):
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        if validate_dimension:
            # Once per process (this class is a cached singleton — see
            # app/api/deps.py), not once per request.
            validate_embedding_dimension(embedding_provider, embedding_dim)
        self._ensure_collection(embedding_dim)
        self._embeddings = LangChainEmbeddingsAdapter(embedding_provider)
        self._store = LCQdrant(
            client=self._client,
            collection_name=collection,
            embedding=self._embeddings,
        )

    def _ensure_collection(self, dim: int) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
        docs = [Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)]
        self._store.add_documents(docs, ids=ids)

    def similarity_search(self, query: str, k: int) -> list[RetrievedChunk]:
        results = self._store.similarity_search_with_score(query, k=k)
        chunks = []
        for doc, score in results:
            chunk_id = str(doc.metadata.get("_id") or doc.metadata.get("id") or "")
            chunks.append(
                RetrievedChunk(
                    id=chunk_id, text=doc.page_content, score=float(score), metadata=doc.metadata
                )
            )
        return chunks

    def ping(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False
