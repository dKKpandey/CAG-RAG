# Architecture

## Why CAG and RAG are both here

RAG answers "what's true right now" by embedding the query and searching a
vector store at request time. That's the right tool for anything that
changes — prices, tickets, live system status — but it pays an embedding +
search + prompt-reprocessing cost on every single request, even for facts
that never change (a handbook, a product warranty policy).

CAG answers "what's always true" by preparing that stable content once and
reusing it. The two aren't competing techniques; they're the cold path and
the hot path of the same context window. This service runs both and merges
them into one final prompt.

| | CAG (cold) | RAG (hot) |
|---|---|---|
| Source | `data/cold_sources/` | `data/hot_sources/` or `POST /v1/documents` |
| When it runs | Once, at setup, or whenever cold sources change | On every query |
| Store | Redis (`app/cache`) | Qdrant (`app/vectorstore`) |
| Entry point | `python -m app.scripts.preload_cache` | automatic, inside `pipeline.answer()` |

## Request flow

```
                      ┌─────────────────────┐
  (once, offline)     │   Cold sources       │
  preload_cache.py ──▶│   (data/cold_sources)│──▶ encode & assemble ──▶ Redis
                      └─────────────────────┘                          │
                                                                        │ get_cached_context()
                                                                        ▼
POST /v1/query  ──▶ embed query ──▶ Qdrant similarity_search() ──▶ compose_messages() ──▶ LLMProvider.generate() ──▶ answer
                     (app/pipeline/rag.py)                         (app/pipeline/composer.py)   (app/llm/*)
```

`app/pipeline/orchestrator.py` is the only place that ties these together —
everything else is a narrow, swappable piece behind an interface:

- `app/cache/base.py` — `CacheStore` (Redis is the only implementation; swap
  in anything key-value)
- `app/vectorstore/base.py` — `VectorStore` (Qdrant is the only
  implementation; the interface has no Qdrant-specific leakage)
- `app/llm/base.py` — `LLMProvider` (Anthropic and OpenAI implementations)
- `app/embeddings/base.py` — `EmbeddingProvider` (Voyage and OpenAI
  implementations)

## Real prompt caching, not just a Redis lookup

Redis in this design is **not** the thing that makes generation cheaper —
it's just where the assembled cold-context text survives a restart. The
actual latency/cost win comes from the LLM provider's own prompt cache:

- **Anthropic**: `app/llm/anthropic_provider.py` marks the cached-context
  block with `cache_control: {"type": "ephemeral"}`. Anthropic will reuse the
  KV-cache for that exact prefix across requests, so you're billed/processed
  for it once per cache TTL (currently 5 minutes, refreshed on each hit)
  instead of on every query.
- **OpenAI**: no explicit opt-in exists; OpenAI automatically caches
  identical prompt prefixes of 1024+ tokens. `OpenAIProvider` relies on the
  same effect by keeping the cached block first and byte-identical.

This is why `app/pipeline/composer.py` is strict about ordering: **the
cached block must come first and must never contain anything that varies
per-request** (no timestamps, no request IDs). Everything that does vary —
retrieved documents, the user's question — comes after it.

## Why two separate stores instead of one

A single vector store could technically hold both the cold and hot
documents. Keeping them apart is deliberate:

1. **Different lifecycles.** Cold sources are curated and change rarely;
   mixing them with live, possibly noisy hot documents makes it harder to
   reason about what's guaranteed to be in every prompt.
2. **Different cost profile.** The cold context is reused verbatim every
   request (ideal for prompt caching); the retrieved context is different
   every time by design, so caching doesn't apply to it.
3. **Operational safety.** You can wipe and re-ingest the hot vector store
   at any time without touching the cache that guarantees baseline answers
   keep working.

## Where this is intentionally incomplete

This is a reference implementation, not a hardened production deployment.
Before shipping it for real traffic, you'd still want: streaming responses,
per-tenant auth instead of one shared API key, rate limiting, retries with
backoff around provider calls, observability (traces/metrics, not just
logs), and a real document-management flow for hot ingestion (delete /
versioning, not just upsert).
