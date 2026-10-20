import hashlib
import json
import logging
from pathlib import Path

from app.cache.base import CacheStore
from app.core.errors import CacheNotPreloadedError

logger = logging.getLogger(__name__)

_TEXT_SUFFIXES = {".md", ".txt"}


def _cache_key(prefix: str, version: str) -> str:
    return f"{prefix}:{version}"


def preload_cold_sources(
    cache_store: CacheStore,
    source_dir: str,
    prefix: str,
    version: str,
    max_chars: int,
) -> dict:
    """Step 1-2 of CAG: read every cold source once, assemble it into a single
    stable text block, and store it. Re-run this whenever the cold sources
    change — it's idempotent and cheap; it is NOT run on every request."""

    paths = sorted(p for p in Path(source_dir).glob("**/*.*") if p.suffix.lower() in _TEXT_SUFFIXES)
    if not paths:
        raise FileNotFoundError(f"No .md/.txt cold sources found under '{source_dir}'")

    sections: list[str] = []
    files: list[str] = []
    for path in paths:
        content = path.read_text(encoding="utf-8").strip()
        sections.append(f"### Source: {path.name}\n{content}")
        files.append(str(path))

    assembled = "\n\n".join(sections)
    if len(assembled) > max_chars:
        logger.warning("Cold context truncated from %d to %d chars", len(assembled), max_chars)
        assembled = assembled[:max_chars]

    content_hash = hashlib.sha256(assembled.encode("utf-8")).hexdigest()[:16]
    payload = {"text": assembled, "hash": content_hash, "files": files}

    cache_store.set(_cache_key(prefix, version), json.dumps(payload))
    logger.info(
        "Preloaded %d cold source(s) (%d chars, hash=%s) into the CAG cache",
        len(files),
        len(assembled),
        content_hash,
    )
    return payload


def get_cached_context(cache_store: CacheStore, prefix: str, version: str) -> str:
    """Step 1 at request time: a pure cache lookup, no re-encoding, no
    re-reading the cold sources."""

    raw = cache_store.get(_cache_key(prefix, version))
    if not raw:
        raise CacheNotPreloadedError(
            "No cached context found. Run `python -m app.scripts.preload_cache` "
            "(or POST /v1/admin/preload-cache) before serving queries."
        )
    payload = json.loads(raw)
    return payload["text"]
