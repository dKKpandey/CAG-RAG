from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class ChatBlock:
    """One piece of message content. `cacheable=True` is a hint to providers
    that support prompt caching (e.g. Anthropic) that this block is stable
    across requests and worth caching server-side."""

    text: str
    cacheable: bool = False


@dataclass
class ChatMessage:
    role: Role
    blocks: list[ChatBlock] = field(default_factory=list)

    @classmethod
    def text(cls, role: Role, text: str, cacheable: bool = False) -> "ChatMessage":
        return cls(role=role, blocks=[ChatBlock(text=text, cacheable=cacheable)])


@dataclass
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage
    cache_hit: bool = False


class LLMProvider(ABC):
    """Provider-agnostic seam for generation. Implementations may use
    LangChain chat models internally, but callers never depend on that."""

    @abstractmethod
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse: ...

    @abstractmethod
    def stream(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Yield response text incrementally. Not covered by the provider
        retry policy — see each implementation's docstring."""
        ...
