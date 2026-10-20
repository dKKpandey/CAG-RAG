# Integration tests

These tests talk to a **real** Redis and a **real** Qdrant — no fakes, no
mocks. They use `tests.fakes.FakeEmbeddingProvider` (deterministic,
hash-based vectors) instead of a real embedding API, so they run without
any paid API key.

They are excluded from the default `pytest` run (see `addopts` in
`pyproject.toml`) and skip themselves cleanly if the services aren't
reachable, rather than failing — so plain `pytest -v` works with zero
setup, same as before.

Run them locally:

```bash
docker compose up -d redis qdrant
pytest -v -m integration
```

They also run automatically in CI (`.github/workflows/ci.yml`, the
`integration` job), against `redis:7-alpine` and `qdrant/qdrant` service
containers — so "this actually talks to real Redis and real Qdrant" is a
claim backed by a CI run on every push, not just a unit test against a
fake.

What's intentionally **not** covered here: real LLM or embedding provider
calls. Those need a paid API key that isn't (and shouldn't be) checked into
this repo. See `scripts/smoke_test.py` for a script a developer runs
themselves, with their own keys, to verify that side end-to-end.
