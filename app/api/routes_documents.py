from fastapi import APIRouter, Depends

from app.api.deps import get_vector_store
from app.core.config import Settings, get_settings
from app.core.security import require_api_key
from app.ingestion.loaders import load_and_chunk_texts
from app.schemas.models import IngestRequest, IngestResponse
from app.vectorstore.base import VectorStore

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
def ingest_documents(
    payload: IngestRequest,
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    """Hot ingestion: add or refresh live documents the RAG side will
    retrieve against. This is independent of (and can run far more often
    than) the one-time CAG cache preload."""

    texts = [
        (doc.text, {**doc.metadata, **({"doc_id": doc.id} if doc.id else {})})
        for doc in payload.documents
    ]
    ids, chunks, metadatas = load_and_chunk_texts(
        texts, settings.chunk_size, settings.chunk_overlap
    )
    vector_store.upsert(ids, chunks, metadatas)
    return IngestResponse(ingested=len(chunks))
