import argparse
import logging

from app.cache.redis_store import RedisCacheStore
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.pipeline.cag import preload_cold_sources


def main() -> None:
    configure_logging()
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Preload cold sources into the CAG cache. Run once at setup, "
        "and again whenever the cold sources change."
    )
    parser.add_argument("--source", default=settings.cold_source_dir)
    args = parser.parse_args()

    cache_store = RedisCacheStore(settings.redis_url)
    payload = preload_cold_sources(
        cache_store,
        args.source,
        settings.cache_key_prefix,
        settings.cache_key_version,
        max_chars=settings.cached_context_max_tokens * 4,
    )
    logging.getLogger(__name__).info(
        "Done. %d file(s) cached, hash=%s", len(payload["files"]), payload["hash"]
    )


if __name__ == "__main__":
    main()
