import logging

from fastapi import FastAPI

from app.api.routes_admin import router as admin_router
from app.api.routes_documents import router as documents_router
from app.api.routes_health import router as health_router
from app.api.routes_query import router as query_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Reference CAG + RAG service: Redis-backed cached context, "
        "Qdrant-backed live retrieval."
    ),
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(query_router)
app.include_router(documents_router)
app.include_router(admin_router)


@app.get("/", tags=["health"])
def root() -> dict:
    return {"service": settings.app_name, "status": "running"}
