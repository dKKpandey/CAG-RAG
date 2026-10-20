from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ClientContext:
    """Who's calling, resolved from X-API-Key. One API key maps to one
    client_id, which is what rate limiting and budget tracking key off —
    never the raw key itself, so it's safe to log client_id."""

    client_id: str
    api_key: str


def _load_key_map(settings: Settings) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if settings.api_key:
        mapping[settings.api_key] = "default"
    for pair in settings.api_keys.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, client_id = pair.partition(":")
        key = key.strip()
        if key:
            mapping[key] = client_id.strip() or key
    return mapping


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ClientContext:
    settings = get_settings()
    key_map = _load_key_map(settings)
    if not x_api_key or x_api_key not in key_map:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
        )
    return ClientContext(client_id=key_map[x_api_key], api_key=x_api_key)
