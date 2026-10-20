import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_authenticated_client, get_cache_store, get_pipeline
from app.cache.base import CacheStore
from app.core.budget import record_usage
from app.core.security import ClientContext
from app.pipeline.orchestrator import CagRagPipeline
from app.schemas.models import QueryRequest, QueryResponse

router = APIRouter(prefix="/v1/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    client: ClientContext = Depends(get_authenticated_client),
    pipeline: CagRagPipeline = Depends(get_pipeline),
    cache_store: CacheStore = Depends(get_cache_store),
) -> QueryResponse:
    response = pipeline.answer(payload.query, payload.top_k)
    total_tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
    record_usage(cache_store, client.client_id, total_tokens)
    return response


@router.post("/stream")
def query_stream(
    payload: QueryRequest,
    client: ClientContext = Depends(get_authenticated_client),
    pipeline: CagRagPipeline = Depends(get_pipeline),
) -> StreamingResponse:
    """Server-Sent Events: a `sources` event as soon as retrieval finishes,
    then one `token` event per chunk of generated text, then `done`.

    Token-level usage isn't recorded against the budget here — providers
    only report usage once a stream completes, and capturing that cleanly
    needs a provider-level "final chunk" contract this reference doesn't
    implement yet. Streaming requests are rate-limited but not
    budget-metered; see docs/architecture-design.md Open Questions.
    """

    def event_source():
        for event in pipeline.answer_stream(payload.query, payload.top_k):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
