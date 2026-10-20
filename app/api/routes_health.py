import logging

from fastapi import APIRouter

from app.api import deps
from app.schemas.models import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """A health check must never 500, even if a dependency is unconfigured
    or unreachable — that's exactly the condition it exists to report. So
    each check is isolated here instead of resolved as a FastAPI Depends()
    (which would raise before this function body ever ran)."""

    redis_ok = False
    try:
        redis_ok = deps.get_cache_store().ping()
    except Exception:
        logger.exception("Redis health check failed")

    vector_store_ok = False
    try:
        vector_store_ok = deps.get_vector_store().ping()
    except Exception:
        logger.exception("Vector store health check failed")

    return HealthResponse(status="ok", redis_ok=redis_ok, vector_store_ok=vector_store_ok)
