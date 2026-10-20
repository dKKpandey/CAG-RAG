import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that should become a clean HTTP response
    instead of a raw 500 with a stack trace."""

    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CacheNotPreloadedError(AppError):
    """Raised when a query arrives before the CAG cache has been preloaded."""

    status_code = 409


class VectorStoreUnavailableError(AppError):
    status_code = 503


class ProviderError(AppError):
    """Wraps failures from the underlying LLM or embedding provider."""

    status_code = 502


class RateLimitExceededError(AppError):
    """Too many requests from this API key within the current window."""

    status_code = 429


class BudgetExceededError(AppError):
    """This API key has used its configured daily token budget."""

    status_code = 429


class ConfigurationError(AppError):
    """A misconfiguration that would otherwise fail confusingly later
    (e.g. EMBEDDING_DIM not matching the active embedding model)."""

    status_code = 500


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError on %s: %s", request.url.path, exc.message)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
