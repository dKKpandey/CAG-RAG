from fastapi import APIRouter, Depends

from app.api.deps import get_pipeline
from app.core.security import require_api_key
from app.pipeline.orchestrator import CagRagPipeline
from app.schemas.models import QueryRequest, QueryResponse

router = APIRouter(prefix="/v1/query", tags=["query"])


@router.post("", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
def query(payload: QueryRequest, pipeline: CagRagPipeline = Depends(get_pipeline)) -> QueryResponse:
    return pipeline.answer(payload.query, payload.top_k)
