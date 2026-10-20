from collections.abc import Iterator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.retry import with_provider_retries
from app.llm.base import ChatMessage, LLMProvider, LLMResponse, LLMUsage


class AnthropicProvider(LLMProvider):
    """Generation via Claude. Blocks marked `cacheable=True` get an Anthropic
    `cache_control: {"type": "ephemeral"}` breakpoint, so a stable CAG context
    block is only billed and re-processed once per cache TTL instead of on
    every request — this is the literal mechanism behind "cache augmented
    generation" when you don't control the model's KV-cache directly.

    For a cache hit to occur, the cached block's content must be byte-identical
    across requests and come before anything that varies per request (see
    app/pipeline/composer.py for how the prompt is ordered).
    """

    def __init__(self, api_key: str, model: str):
        self._client = ChatAnthropic(model=model, api_key=api_key, max_tokens=1024)

    def _to_langchain_message(self, message: ChatMessage) -> BaseMessage:
        content = []
        for block in message.blocks:
            item = {"type": "text", "text": block.text}
            if block.cacheable:
                item["cache_control"] = {"type": "ephemeral"}
            content.append(item)

        if message.role == "system":
            return SystemMessage(content=content)
        if message.role == "assistant":
            return AIMessage(content=content)
        return HumanMessage(content=content)

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

        if isinstance(result.content, str):
            text = result.content
        else:
            text = "".join(
                part.get("text", "") for part in result.content if isinstance(part, dict)
            )

        usage_meta = getattr(result, "usage_metadata", None) or {}
        input_details = usage_meta.get("input_token_details", {}) if usage_meta else {}
        cache_read = input_details.get("cache_read", 0) or 0
        cache_creation = input_details.get("cache_creation", 0) or 0

        usage = LLMUsage(
            input_tokens=usage_meta.get("input_tokens"),
            output_tokens=usage_meta.get("output_tokens"),
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
        )
        return LLMResponse(text=text, usage=usage, cache_hit=cache_read > 0)

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Not wrapped in the provider retry policy: once tokens have started
        reaching the client, re-running the whole call on a mid-stream error
        would duplicate output rather than recover cleanly."""
        lc_messages = [self._to_langchain_message(m) for m in messages]
        stream = self._client.stream(lc_messages, max_tokens=max_tokens, temperature=temperature)
        for chunk in stream:
            if isinstance(chunk.content, str):
                if chunk.content:
                    yield chunk.content
            else:
                for part in chunk.content:
                    if isinstance(part, dict) and part.get("text"):
                        yield part["text"]
