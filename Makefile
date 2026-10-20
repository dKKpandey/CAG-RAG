.PHONY: install dev test test-integration lint up down preload ingest quickstart smoke-test

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -v

test-integration:
	pytest -v -m integration

lint:
	ruff check .

up:
	docker compose up -d redis qdrant

down:
	docker compose down

preload:
	python -m app.scripts.preload_cache

ingest:
	python -m app.scripts.ingest_documents

quickstart:
	./scripts/quickstart.sh

# Usage: make smoke-test API_KEY=dev-local-key
smoke-test:
	python scripts/smoke_test.py --api-key $(API_KEY)
