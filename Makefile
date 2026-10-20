.PHONY: install dev test lint up down preload ingest

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -v

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
