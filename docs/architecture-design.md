# Architecture Design Document — CAG + RAG Reference Service

| | |
|---|---|
| **Status** | Accepted |
| **Owner** | Kamal Pandey |
| **Scope** | `cag-rag-reference-architecture` (this repository) |
| **Last updated** | 2026-10-20 |

## Table of Contents

1. [Summary](#1-summary)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [Problem Statement](#3-problem-statement)
4. [System Context](#4-system-context)
5. [Architecture Overview](#5-architecture-overview)
6. [Component Design](#6-component-design)
7. [Request Lifecycle](#7-request-lifecycle)
8. [Offline Data Pipelines](#8-offline-data-pipelines)
9. [Caching Strategy](#9-caching-strategy)
10. [Data & API Contracts](#10-data--api-contracts)
11. [Deployment View](#11-deployment-view)
12. [Security Model](#12-security-model)
13. [Reliability & Failure Modes](#13-reliability--failure-modes)
14. [Scalability Considerations](#14-scalability-considerations)
15. [Design Alternatives Considered](#15-design-alternatives-considered)
16. [Testing Strategy](#16-testing-strategy)
17. [Open Questions & Future Work](#17-open-questions--future-work)
18. [References](#18-references)

---

## 1. Summary

This service answers a query by combining two different ways of giving an
LLM context: **Cache Augmented Generation (CAG)**, which preloads stable,
rarely-changing knowledge once, and **Retrieval Augmented Generation
(RAG)**, which searches live, frequently-changing knowledge on every
request. Both are merged into a single prompt that an LLM provider turns
into a grounded answer.

The system is a single FastAPI service backed by Redis (the CAG cache) and
Qdrant (the RAG vector store), with the LLM and embedding calls routed
through provider-agnostic interfaces so the generation and embedding
vendors can be swapped without touching application logic.

## 2. Goals and Non-Goals

**Goals**

- Serve answers that combine durable, curated knowledge with fresh,
  frequently-changing knowledge, in one prompt.
- Make the cold (CAG) and hot (RAG) paths operationally independent: the
  cache can be rebuilt without touching the vector store, and vice versa.
- Keep the LLM and embedding vendor swappable behind a narrow interface —
  no code outside `app/llm/` and `app/embeddings/` should know which
  vendor is active.
- Get real benefit from LLM provider-side prompt caching (not just an
  internal Redis cache) by controlling prompt structure and ordering.
- Be runnable and testable without any cloud credentials (fakes for every
  external dependency).

**Non-Goals**

- Multi-tenant isolation (one shared API key, one cache namespace).
- Streaming responses.
- A document-management UI, versioning, or deletion workflow for the
  vector store beyond upsert.
- High-availability Redis/Qdrant topologies (single-node Compose setup).
- Prompt-injection or jailbreak defenses beyond a scoped system prompt.

## 3. Problem Statement

A pure RAG system pays an embedding + vector-search + full-prompt-reprocessing
cost on *every single request*, even for facts that never change — a
company handbook, a warranty policy. A pure CAG system (everything
preloaded once) goes stale the moment anything changes, and can't answer
questions about today's data.

Neither technique alone is sufficient for a system that needs both a
stable knowledge baseline and live facts. This service treats them as two
complementary paths into the same context window rather than competing
architectures, and is deliberately built to make that combination — not
just RAG, and not just CAG — the thing under test.

## 4. System Context

```mermaid
flowchart LR
    Client(["Client\n(curl / frontend)"])
    subgraph Svc["CAG + RAG Service"]
        App["FastAPI app\n:8000"]
    end
    Redis[("Redis\nCAG cache")]
    Qdrant[("Qdrant\nRAG vectors")]
    LLM["LLM Provider (SaaS)\nAnthropic Claude / OpenAI GPT"]
    Embed["Embedding Provider (SaaS)\nVoyage AI / OpenAI Embeddings"]

    Client -- "HTTPS, X-API-Key" --> App
    App --> Redis
    App --> Qdrant
    App -- "generate()" --> LLM
    App -- "embed_query() / embed_documents()" --> Embed
```

The service owns Redis and Qdrant (both run alongside it in Docker
Compose); the LLM and embedding providers are external SaaS dependencies
reached over the internet.

## 5. Architecture Overview

![Operational architecture diagram](images/operational-architecture.svg)

The diagram above is the deployment-level view: the live request path
(solid arrows, numbered 1–6) through auth, the pipeline, Redis, Qdrant and
the two external providers; and the offline/admin path (dashed arrows) run
via the two CLI scripts, outside the request path entirely.

## 6. Component Design

```mermaid
flowchart TB
    subgraph Routers["app/api/*"]
        R1["GET /health"]
        R2["POST /v1/query"]
        R3["POST /v1/documents"]
        R4["POST /v1/admin/preload-cache"]
    end
    Auth["require_api_key()\napp/core/security.py"]
    Pipeline["CagRagPipeline\napp/pipeline/orchestrator.py"]
    CacheStore["CacheStore (ABC)\n→ RedisCacheStore"]
    VectorStore["VectorStore (ABC)\n→ QdrantStore"]
    EmbedProv["EmbeddingProvider (ABC)\n→ Voyage / OpenAI"]
    LLMProv["LLMProvider (ABC)\n→ Anthropic / OpenAI"]

    R2 --> Auth --> Pipeline
    R3 --> Auth
    R4 --> Auth
    Pipeline --> CacheStore
    Pipeline --> VectorStore
    Pipeline --> LLMProv
    VectorStore --> EmbedProv
```

| Component | File | Responsibility |
|---|---|---|
| Routers | `app/api/routes_*.py` | HTTP surface; thin, no business logic |
| `require_api_key` | `app/core/security.py` | Shared-secret auth, applied to every route but `/health` |
| `CagRagPipeline` | `app/pipeline/orchestrator.py` | The one place that sequences cache lookup → retrieval → compose → generate |
| `CacheStore` | `app/cache/base.py`, `redis_store.py` | Durable store for the assembled cold-context block |
| `VectorStore` | `app/vectorstore/base.py`, `qdrant_store.py` | Live similarity search + upsert over hot documents |
| `EmbeddingProvider` | `app/embeddings/base.py`, `voyage_provider.py`, `openai_provider.py` | Turns text into vectors, for both ingestion and query time |
| `LLMProvider` | `app/llm/base.py`, `anthropic_provider.py`, `openai_provider.py` | Generation; owns provider-specific prompt-caching mechanics |

Every arrow in the diagram above is an interface, not a concrete class —
`CagRagPipeline` is constructed with whatever `CacheStore`/`VectorStore`/
`LLMProvider` implementation `app/api/deps.py` wires up from `Settings`.
Tests substitute `tests/fakes.py` implementations at exactly this seam.

## 7. Request Lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI routes
    participant P as CagRagPipeline
    participant R as Redis (CacheStore)
    participant Q as Qdrant (VectorStore)
    participant E as EmbeddingProvider
    participant L as LLMProvider

    C->>A: POST /v1/query {query, top_k?}
    A->>A: require_api_key()
    A->>P: answer(query, top_k)
    P->>R: get_cached_context()
    R-->>P: cached context text
    P->>Q: similarity_search(query, k)
    Q->>E: embed_query(query)
    E-->>Q: query vector
    Q-->>P: retrieved chunks + scores
    P->>P: compose_messages(cached, retrieved, query)
    P->>L: generate(messages)
    L-->>P: answer text + usage (+ cache_hit)
    P-->>A: QueryResponse
    A-->>C: 200 {answer, sources, cache_hit, usage}
```

If `get_cached_context()` finds nothing (the cache was never preloaded),
`CacheNotPreloadedError` short-circuits the request with `409 Conflict`
before any embedding or generation call is made — a configuration error,
not a transient failure, should fail fast and cheaply.

## 8. Offline Data Pipelines

The cold (CAG) and hot (RAG) paths are populated by two independent CLI
jobs, never by the request path itself:

```mermaid
flowchart LR
    subgraph Cold["CAG: run once, or when cold sources change"]
        CS["data/cold_sources/*.md"] --> PC["preload_cache.py"] --> R1[("Redis")]
    end
    subgraph Hot["RAG: run whenever hot sources change"]
        HS["data/hot_sources/*.md"] --> ID["ingest_documents.py"] --> EP["EmbeddingProvider"] --> Q1[("Qdrant")]
    end
```

`preload_cache.py` reads every `.md`/`.txt` file under `COLD_SOURCE_DIR`,
concatenates them into one block (truncated to `CACHED_CONTEXT_MAX_TOKENS`
if needed), hashes it, and stores it as JSON in Redis — idempotent, so
re-running it is always safe. `ingest_documents.py` chunks every file under
a hot-source directory (`RecursiveCharacterTextSplitter`) and upserts the
chunks into Qdrant; `POST /v1/documents` does the same thing per-request
for programmatic ingestion.

## 9. Caching Strategy

Redis is **not** what makes generation cheaper — it only makes the
assembled cold-context text survive a restart. The actual latency/cost win
comes from the LLM provider's own prompt cache, and getting it requires
controlling prompt structure:

- **Anthropic**: `AnthropicProvider` marks the cached-context block with
  `cache_control: {"type": "ephemeral"}`. Anthropic reuses the KV-cache
  for that exact prefix across requests — billed and reprocessed once per
  cache TTL instead of on every query.
- **OpenAI**: no explicit opt-in exists; OpenAI automatically caches
  identical prompt prefixes of 1024+ tokens. `OpenAIProvider` gets the same
  effect for free by preserving the same ordering.

This is why `app/pipeline/composer.py` is strict about prompt structure:
**the cached block must be byte-identical across requests and must come
before anything that varies per request.** Retrieved documents and the
user's question always come after it, never inside it.

```mermaid
flowchart LR
    Cached["Cached context\n(stable, cache_control=ephemeral)"] --> Retrieved["Retrieved context\n(varies per request)"] --> Query["User query\n(varies per request)"] --> Prompt["Final prompt → LLM"]
```

## 10. Data & API Contracts

**Cache key**: `{CACHE_KEY_PREFIX}:{CACHE_KEY_VERSION}` (default
`cag:cached_context:v1`) → JSON `{text, hash, files}`. Bumping
`CACHE_KEY_VERSION` is the escape hatch for a breaking change to the
assembled format without deleting the old key.

**Qdrant collection**: one collection (`QDRANT_COLLECTION`), cosine
distance, vector size fixed to `EMBEDDING_DIM` — which **must** match
whatever embedding model is actually configured; there is no runtime
dimension check beyond what Qdrant itself enforces on insert.

**`POST /v1/query`**

```json
// request
{ "query": "How many PTO days do I get?", "top_k": 4 }
// response
{
  "answer": "...",
  "sources": [{ "id": "...", "text": "...", "score": 0.91, "metadata": {} }],
  "cache_hit": true,
  "usage": { "input_tokens": 812, "output_tokens": 64, "cache_read_input_tokens": 640 }
}
```

**`POST /v1/documents`** — `{"documents": [{"text": "...", "metadata"?: {}}]}`
→ `{"ingested": <chunk count>}`.

**`POST /v1/admin/preload-cache`** — no body →
`{"cached_chars": ..., "source_files": [...], "content_hash": "..."}`.

Full schemas: `app/schemas/models.py`.

## 11. Deployment View

```mermaid
flowchart TB
    subgraph Compose["docker-compose.yml — cag-rag-stack"]
        AppC["app\nFastAPI :8000"]
        RedisC[("redis:7-alpine\n:6379")]
        QdrantC[("qdrant:v1.9.2\n:6333")]
    end
    Client(("Client")) -- ":8000" --> AppC
    AppC --> RedisC
    AppC --> QdrantC
    AppC -. HTTPS .-> LLMExt["LLM Provider SaaS"]
    AppC -. HTTPS .-> EmbedExt["Embedding Provider SaaS"]
```

Single Compose stack, three services, two named volumes
(`redis_data`, `qdrant_data`) for persistence across restarts. The app
image is built from the repo's `Dockerfile`; `preload_cache.py` and
`ingest_documents.py` are run via `docker compose exec app python -m ...`
rather than as containers of their own.

## 12. Security Model

- Every route but `/health` requires `X-API-Key` to match `Settings.api_key`
  (`app/core/security.py`) — one shared secret, no per-caller identity.
- Provider API keys (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, etc.) live only
  in `.env` (gitignored); `.env.example` ships with every value blank.
- `/health` is intentionally unauthenticated and never throws — see
  [§13](#13-reliability--failure-modes).
- Out of scope today: per-caller rate limiting, request signing, and
  prompt-injection defenses beyond the scoped system prompt in
  `composer.py`.

## 13. Reliability & Failure Modes

| Failure | Behavior | Why |
|---|---|---|
| Cache never preloaded | `POST /v1/query` → `409` before any provider call | `CacheNotPreloadedError`; a config error, not transient |
| Redis unreachable | `GET /health` reports `redis_ok: false`, no 500 | Checks are isolated per-dependency in the handler body, not resolved as `Depends()` (which would raise before the handler runs) |
| Qdrant unreachable | Same as above for `vector_store_ok` | Same isolation pattern |
| Missing provider API key | Raised only when that provider is actually constructed (first real use), not at process startup | Keeps `/health` and unrelated routes usable even if one provider is unconfigured |
| LLM/embedding provider error | Propagates as an unhandled exception today | No retry/backoff yet — see [§17](#17-open-questions--future-work) |

## 14. Scalability Considerations

- The app is stateless per request (all state lives in Redis/Qdrant), so
  it scales horizontally by running more `app` containers behind a load
  balancer with no code changes.
- Redis and Qdrant are each single-node in this reference setup; the cache
  is small (one text blob) and would need Redis Cluster/Sentinel only for
  HA, not for size. Qdrant is the component most likely to need real
  scaling (sharding/replication) as the hot document set grows.
- `top_k` and `chunk_size`/`chunk_overlap` are the main levers for
  controlling per-query latency and prompt size as the corpus grows.

## 15. Design Alternatives Considered

| Decision | Alternative | Why rejected |
|---|---|---|
| Two separate stores (Redis + Qdrant) | One vector store holding both cold and hot documents | Mixes two different lifecycles and cost profiles; see `ARCHITECTURE.md` §"Why two separate stores" |
| Provider-agnostic `LLMProvider`/`EmbeddingProvider` interfaces | Call LangChain's chat model classes directly everywhere | Would leak a specific library's abstraction (and its breaking changes) into every call site instead of one factory |
| CLI scripts for preload/ingest | Run preload/ingest automatically on app startup | Makes startup slow and non-idempotent-feeling, and conflates "deploy the service" with "refresh the data" — two different operational events |
| Cache key with explicit version suffix | Unversioned key | Lets the assembled-cache format change without a manual `DEL` in Redis |
| Shared single API key | Per-caller keys / OAuth | Out of scope for a reference service; noted as a real gap, not solved |

## 16. Testing Strategy

Every external dependency has a fake (`tests/fakes.py`): `FakeCacheStore`,
`FakeVectorStore`, `FakeLLMProvider`. The suite never calls a real API or
needs Redis/Qdrant running — `pytest -v` passes with zero configuration.
API-level tests use FastAPI's `dependency_overrides` (for `Depends()`-based
routes) or `monkeypatch` on `app.api.deps` directly (for `/health`, which
deliberately isn't a `Depends()` so it can catch its own exceptions — see
`tests/test_api.py::test_health_endpoint_reports_false_instead_of_crashing_when_unconfigured`
for the regression test behind that design choice).

## 17. Open Questions & Future Work

- Streaming responses (`generate()` currently returns a complete string).
- Retry/backoff around provider calls (`tenacity` or similar).
- Per-caller auth instead of one shared `API_KEY`.
- A real delete/versioning story for hot documents in Qdrant (today only
  upsert exists).
- Observability: structured tracing/metrics, not just `logging`.
- Automatic dimension validation between the configured embedding model
  and `EMBEDDING_DIM`/the Qdrant collection, instead of relying on the
  operator to keep them in sync.

## 18. References

- [`README.md`](../README.md) — quickstart, API table, project layout
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — shorter companion explainer,
  focused on the CAG/RAG rationale
- Source of truth for every claim in this document is the code itself,
  under `app/`
