
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore as LCQdrant
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.embeddings.base import EmbeddingProvider
from app.embeddings.langchain_adapter import LangChainEmbeddingsAdapter
from app.vectorstore.base import RetrievedChunk, VectorStore


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
    ):
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
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
