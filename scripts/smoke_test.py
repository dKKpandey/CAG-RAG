"""End-to-end smoke test against a *running* instance with *real* provider
keys configured. This is the one check in this repo that Claude could not
run itself — it needs your paid Anthropic/Voyage/OpenAI keys and a live
server. Run it yourself after `quickstart.sh` and `uvicorn app.main:app`:

    python scripts/smoke_test.py --api-key dev-local-key

It does not assert anything that depends on a *specific* answer (models
change), only on the *shape* and *mechanics* being correct: health is up,
a query returns a well-formed response, ingestion + retrieval actually
finds a just-ingested document, and — the thing this whole repo is about —
sending the same query twice shows a real prompt-cache hit the second time.
"""

import argparse
import sys
import time

import httpx


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--query", default="How many PTO days do I get?")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=60.0)
    headers = {"X-API-Key": args.api_key, "Content-Type": "application/json"}
    all_ok = True

    print(f"Target: {args.base_url}\n")

    # 1. Health
    resp = client.get("/health")
    body = resp.json() if resp.status_code == 200 else {}
    all_ok &= check("GET /health returns 200", resp.status_code == 200)
    all_ok &= check("Redis reachable", body.get("redis_ok") is True, str(body))
    all_ok &= check("Vector store reachable", body.get("vector_store_ok") is True, str(body))

    # 2. Ingest a document only this test knows about, so retrieval has
    #    something unambiguous to find.
    marker = f"smoke-test-marker-{int(time.time())}"
    ingest_resp = client.post(
        "/v1/documents",
        headers=headers,
        json={"documents": [{"text": f"The secret code for today is {marker}."}]},
    )
    all_ok &= check(
        "POST /v1/documents returns 200", ingest_resp.status_code == 200, ingest_resp.text
    )

    # 3. Query for it and confirm it comes back as a source.
    find_resp = client.post(
        "/v1/query", headers=headers, json={"query": "What is the secret code for today?"}
    )
    find_body = find_resp.json() if find_resp.status_code == 200 else {}
    found = any(marker in s.get("text", "") for s in find_body.get("sources", []))
    all_ok &= check(
        "Just-ingested document is retrieved as a source", found, str(find_body.get("sources"))
    )

    # 4. The real point of this repo: send the *same* query twice and
    #    confirm the second call reports a cache hit. First call also
    #    establishes that /v1/query works end-to-end with real providers.
    first = client.post("/v1/query", headers=headers, json={"query": args.query})
    first_body = first.json() if first.status_code == 200 else {}
    all_ok &= check("POST /v1/query returns 200", first.status_code == 200, first.text)
    all_ok &= check(
        "Response has a non-empty answer", bool(first_body.get("answer")), str(first_body)
    )

    second = client.post("/v1/query", headers=headers, json={"query": args.query})
    second_body = second.json() if second.status_code == 200 else {}
    cache_hit = second_body.get("cache_hit") is True
    usage = second_body.get("usage", {})
    all_ok &= check(
        "Second identical query reports cache_hit=true",
        cache_hit,
        f"usage={usage} — if this fails, check LLM_PROVIDER/the cached block "
        "is identical across requests (see composer.py)",
    )

    print()
    if all_ok:
        print("All checks passed. CAG + RAG is working end-to-end with your real keys.")
    else:
        print("One or more checks failed — see [FAIL] lines above.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
