from collections.abc import Iterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.retry import with_provider_retries
from app.llm.base import ChatMessage, LLMProvider, LLMResponse, LLMUsage


class OpenAIProvider(LLMProvider):
    """Generation via an OpenAI chat model. OpenAI has no explicit
    cache_control API: it automatically reuses the KV-cache for identical
    prompt prefixes of 1024+ tokens. We get most of the same CAG benefit for
    free as long as the stable cached-context block stays first and
    byte-identical across requests (see app/pipeline/composer.py)."""

    def __init__(self, api_key: str, model: str):
        self._client = ChatOpenAI(model=model, api_key=api_key)

    def _flatten(self, message: ChatMessage) -> str:
        return "\n\n".join(block.text for block in message.blocks)

    def _to_langchain_message(self, message: ChatMessage) -> BaseMessage:
        text = self._flatten(message)
        if message.role == "system":
            return SystemMessage(content=text)
        return HumanMessage(content=text)

    @with_provider_retries
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        lc_messages = [self._to_langchain_message(m) for m in messages]
        result = self._client.invoke(lc_messages, max_tokens=max_tokens, temperature=temperature)

        has_meta = hasattr(result, "response_metadata")
        meta = result.response_metadata.get("token_usage", {}) if has_meta else {}
        details = meta.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0

        usage = LLMUsage(
            input_tokens=meta.get("prompt_tokens"),
            output_tokens=meta.get("completion_tokens"),
            cache_read_input_tokens=cached,
        )
        return LLMResponse(text=result.content, usage=usage, cache_hit=bool(cached))

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        lc_messages = [self._to_langchain_message(m) for m in messages]
        stream = self._client.stream(lc_messages, max_tokens=max_tokens, temperature=temperature)
        for chunk in stream:
            if chunk.content:
                yield chunk.content
