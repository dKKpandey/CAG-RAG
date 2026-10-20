#!/usr/bin/env bash
# One-command local setup: start Redis + Qdrant, preload the CAG cache,
# ingest the RAG hot sources. Does NOT start the API server itself (last
# step is interactive by design, so you see its logs) and does NOT touch
# your API keys beyond checking that .env exists.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Add your real LLM/embedding API keys to .env, then re-run this script."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required (for Redis + Qdrant) but was not found on PATH." >&2
  exit 1
fi

echo "==> Starting Redis + Qdrant (docker compose up -d redis qdrant)"
docker compose up -d redis qdrant

echo "==> Waiting for Redis..."
for _ in $(seq 1 30); do
  if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    break
  fi
  sleep 1
done

echo "==> Waiting for Qdrant..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:6333/readyz >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Installing Python dependencies"
pip install -r requirements.txt -q

echo "==> Preloading CAG cache from data/cold_sources/"
python -m app.scripts.preload_cache

echo "==> Ingesting RAG hot sources from data/hot_sources/"
python -m app.scripts.ingest_documents

API_KEY_VALUE="$(grep '^API_KEY=' .env | head -1 | cut -d= -f2-)"

cat <<EOF

==> Setup complete. Start the API with:

    uvicorn app.main:app --reload --port 8000

Then, in another terminal:

    curl -X POST localhost:8000/v1/query \\
      -H "X-API-Key: ${API_KEY_VALUE:-dev-local-key}" \\
      -H "Content-Type: application/json" \\
      -d '{"query": "How many PTO days do I get?"}'

To verify the full stack end-to-end with your real provider keys, see:

    python scripts/smoke_test.py --api-key "${API_KEY_VALUE:-dev-local-key}"
EOF
