# CAG + RAG Reference Service

A real, runnable FastAPI service that combines **Cache Augmented Generation**
(stable knowledge, preloaded once into Redis) with **Retrieval Augmented
Generation** (live knowledge, searched at request time in Qdrant), merges
both into one prompt, and generates an answer via a provider-agnostic LLM
layer (Anthropic or OpenAI).

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together and
why there are two separate stores instead of one, or
[docs/architecture-design.md](docs/architecture-design.md) for the full
design document (system context, component design, sequence diagrams,
deployment view, failure modes, and alternatives considered).

## Before you start: this needs your own paid API keys

This service calls real LLM and embedding providers — Anthropic/OpenAI for
generation, Voyage/OpenAI for embeddings. You need your own account and API
key for at least one of each; using them is your responsibility and your
cost. Nothing in this repo works without them, and nothing here caps what
you spend beyond the guardrails you configure yourself (see
`RATE_LIMIT_PER_MINUTE` / `MAX_DAILY_TOKENS_PER_CLIENT` below).

## Quickstart

```bash
cp .env.example .env
# edit .env: set LLM_PROVIDER, EMBEDDING_PROVIDER and the matching API keys

./scripts/quickstart.sh
```

`quickstart.sh` starts Redis + Qdrant, preloads the CAG cache from
`data/cold_sources/`, and ingests `data/hot_sources/` into Qdrant. It prints
the next command to run (`uvicorn app.main:app --reload --port 8000`) rather
than running it itself, so you see the server's logs directly. Or do the
same thing by hand:

```bash
docker compose up -d redis qdrant
pip install -r requirements.txt

python -m app.scripts.preload_cache          # CAG: preload data/cold_sources/ once
python -m app.scripts.ingest_documents       # RAG: index data/hot_sources/

uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl -X POST localhost:8000/v1/query \
  -H "X-API-Key: dev-local-key" -H "Content-Type: application/json" \
  -d '{"query": "How many PTO days do I get, and is anything degraded right now?"}'
```

The sample `data/cold_sources/` (PTO policy, product warranty — stable) and
`data/hot_sources/` (system status, this week's promo — changes often) are
there so this answers out of the box without needing your own documents.

### Verifying it actually works end-to-end

Everything in this repo's test suite runs against fakes — on purpose, so it
needs no credentials. That also means passing tests don't prove your real
keys, your real Redis/Qdrant, and the real provider APIs all work together.
Once the server is running with your keys:

```bash
python scripts/smoke_test.py --api-key dev-local-key
```

This checks health, ingests a one-off test document and confirms retrieval
actually finds it, and — the specific thing this whole repo is about —
sends the same query twice and confirms the **second call reports a real
prompt-cache hit** from your LLM provider.

## Running everything in Docker

```bash
docker compose up -d
docker compose exec app python -m app.scripts.preload_cache
docker compose exec app python -m app.scripts.ingest_documents
```

## API

All routes except `/health` require `X-API-Key: <API_KEY>` (see `.env`).
Each key is rate-limited and budget-capped independently — see
[Auth, rate limits & budgets](#auth-rate-limits--budgets).

| Route | Purpose |
|---|---|
| `GET /health` | Redis + Qdrant reachability |
| `POST /v1/query` | `{"query": "...", "top_k"?: int}` → answer + sources + cache/usage info |
| `POST /v1/query/stream` | Same input, Server-Sent Events: `sources` → `token`\* → `done` |
| `POST /v1/documents` | `{"documents": [{"text": "...", "metadata"?: {}}]}` — hot ingestion |
| `POST /v1/admin/preload-cache` | Re-run the CAG preload over HTTP |

## Auth, rate limits & budgets

- **Multiple callers**: `API_KEY` is the legacy single key (client_id
  `default`). For more than one caller, set
  `API_KEYS="key1:alice,key2:bob"` in `.env` — each key gets its own
  rate-limit and budget tracking, independent of the others.
- **Rate limiting**: `RATE_LIMIT_PER_MINUTE` (default 60, `0` disables) —
  a fixed-window counter per client_id in Redis. Exceeding it returns `429`.
- **Daily budget**: `MAX_DAILY_TOKENS_PER_CLIENT` (default `0` = unlimited)
  caps total input+output tokens per client_id per UTC day. Set this before
  handing a key to someone else. Returns `429` once exceeded; resets at
  midnight.
- **Retries**: every LLM/embedding call is retried up to 3 times with
  exponential backoff + jitter (`app/core/retry.py`) before the error
  reaches you.

## Development

```bash
pip install -r requirements-dev.txt
pytest -v        # unit + API tests against fakes — no API keys or services needed
ruff check .
```

`tests/fakes.py` provides in-memory stand-ins for the cache store, vector
store, embedding provider, and LLM provider, so the unit test suite never
calls a real API or needs Redis/Qdrant running.

### Integration tests (real Redis + real Qdrant, still no paid keys)

```bash
docker compose up -d redis qdrant
pytest -v -m integration
```

These talk to **real** Redis and Qdrant instances — using a deterministic
fake embedding provider so no paid API key is required — and skip
themselves cleanly if the services aren't running. They also run
automatically in CI against service containers (see
`.github/workflows/ci.yml`'s `integration` job), so "this actually talks to
real Redis and real Qdrant" is backed by a CI run on every push, not just a
unit test against a fake. See `tests/integration/README.md` for details and
for what's still *not* covered (real LLM/embedding calls — that's what
`scripts/smoke_test.py` is for).

## Swapping providers

- LLM: set `LLM_PROVIDER=anthropic|openai` — see `app/llm/`
- Embeddings: set `EMBEDDING_PROVIDER=voyage|openai` — see `app/embeddings/`
- Adding a third provider for either means implementing one class against
  `app/llm/base.py::LLMProvider` or `app/embeddings/base.py::EmbeddingProvider`
  and registering it in the matching `factory.py`. Nothing else in the
  codebase references a concrete provider.
- `EMBEDDING_DIM` must match whatever embedding model you actually configure.
  `VALIDATE_EMBEDDING_DIM=true` (default) checks this once at startup with a
  clear error instead of a confusing Qdrant failure later.

## Project layout

```
app/
  cache/        CacheStore interface + Redis implementation (CAG)
  vectorstore/  VectorStore interface + Qdrant implementation (RAG)
  llm/          LLMProvider interface + Anthropic/OpenAI implementations (generate + stream)
  embeddings/   EmbeddingProvider interface + Voyage/OpenAI implementations
  pipeline/     cag.py, rag.py, composer.py, orchestrator.py — the actual logic
  ingestion/    document loading + chunking for hot ingestion
  core/         config, auth, rate limiting, budget guardrails, retries, errors
  api/          FastAPI routes, dependency wiring
  scripts/      CLI entry points (preload_cache, ingest_documents)
data/
  cold_sources/ example stable documents (CAG)
  hot_sources/  example live documents (RAG)
scripts/
  quickstart.sh   one-command local setup
  smoke_test.py   end-to-end check against your real running stack + keys
tests/
  (unit)        tests against fakes — no credentials or services needed
  integration/  tests against real Redis/Qdrant — no paid API keys needed
```
