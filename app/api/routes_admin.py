from fastapi import APIRouter, Depends

from app.api.deps import get_authenticated_client, get_cache_store
from app.cache.base import CacheStore
from app.core.config import Settings, get_settings
from app.pipeline.cag import preload_cold_sources
from app.schemas.models import PreloadCacheResponse

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post(
    "/preload-cache",
    response_model=PreloadCacheResponse,
    dependencies=[Depends(get_authenticated_client)],
)
def preload_cache(
    cache_store: CacheStore = Depends(get_cache_store),
    settings: Settings = Depends(get_settings),
) -> PreloadCacheResponse:
    """Triggers the CAG preload (steps 1-2) over HTTP. Equivalent to running
    `python -m app.scripts.preload_cache`. Call this once at setup and again
    whenever the cold sources change — never on the hot query path."""

    payload = preload_cold_sources(
        cache_store,
        settings.cold_source_dir,
        settings.cache_key_prefix,
        settings.cache_key_version,
        max_chars=settings.cached_context_max_tokens * 4,
    )
    return PreloadCacheResponse(
        cached_chars=len(payload["text"]),
        source_files=payload["files"],
        content_hash=payload["hash"],
    )
