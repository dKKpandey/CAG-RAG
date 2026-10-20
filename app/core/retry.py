from tenacity import retry, stop_after_attempt, wait_random_exponential

#: Shared retry policy for calls to external LLM/embedding providers:
#: up to 3 attempts, exponential backoff with jitter, capped at 8s between
#: attempts. Broad on purpose (SDKs raise different exception types per
#: vendor) — this is a reference policy, not a tuned one; see
#: docs/architecture-design.md for the tradeoff.
with_provider_retries = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=0.5, max=8),
)
