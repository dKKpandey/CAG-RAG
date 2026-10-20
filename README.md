# CAG + RAG Reference Service

A real, runnable FastAPI service that combines **Cache Augmented Generation**
(stable knowledge, preloaded once into Redis) with **Retrieval Augmented
Generation** (live knowledge, searched at request time in Qdrant), merges
both into one prompt, and generates an answer via a provider-agnostic LLM
layer (Anthropic or OpenAI).

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together and
why there are two separate stores instead of one.

## Quickstart

```bash
cp .env.example .env
# edit .env: set LLM_PROVIDER, EMBEDDING_PROVIDER and the matching API keys

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
there so this answer out of the box without needing your own documents.

## Running everything in Docker

```bash
docker compose up -d
docker compose exec app python -m app.scripts.preload_cache
docker compose exec app python -m app.scripts.ingest_documents
```

## API

All routes except `/health` require `X-API-Key: <API_KEY>` (see `.env`).

| Route | Purpose |
|---|---|
| `GET /health` | Redis + Qdrant reachability |
| `POST /v1/query` | `{"query": "...", "top_k"?: int}` → answer + sources + cache/usage info |
| `POST /v1/documents` | `{"documents": [{"text": "...", "metadata"?: {}}]}` — hot ingestion |
| `POST /v1/admin/preload-cache` | Re-run the CAG preload over HTTP |

## Development

```bash
pip install -r requirements-dev.txt
pytest -v        # all tests run against fakes — no API keys or services needed
ruff check .
```

`tests/fakes.py` provides in-memory stand-ins for the cache store, vector
store and LLM provider, so the test suite never calls a real API or needs
Redis/Qdrant running.

## Swapping providers

- LLM: set `LLM_PROVIDER=anthropic|openai` — see `app/llm/`
- Embeddings: set `EMBEDDING_PROVIDER=voyage|openai` — see `app/embeddings/`
- Adding a third provider for either means implementing one class against
  `app/llm/base.py::LLMProvider` or `app/embeddings/base.py::EmbeddingProvider`
  and registering it in the matching `factory.py`. Nothing else in the
  codebase references a concrete provider.

## Project layout

```
app/
  cache/        CacheStore interface + Redis implementation (CAG)
  vectorstore/  VectorStore interface + Qdrant implementation (RAG)
  llm/          LLMProvider interface + Anthropic/OpenAI implementations
  embeddings/   EmbeddingProvider interface + Voyage/OpenAI implementations
  pipeline/     cag.py, rag.py, composer.py, orchestrator.py — the actual logic
  ingestion/    document loading + chunking for hot ingestion
  api/          FastAPI routes, dependency wiring, auth
  scripts/      CLI entry points (preload_cache, ingest_documents)
data/
  cold_sources/ example stable documents (CAG)
  hot_sources/  example live documents (RAG)
tests/          unit + API tests against fakes
```
