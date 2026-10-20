from abc import ABC, abstractmethod


class CacheStore(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    @abstractmethod
    def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        """Atomically add `amount` to the integer at `key` (starting from 0)
        and return the new value. `ttl` is applied only the first time a key
        is created within a window, matching Redis's INCRBY + conditional
        EXPIRE. Used for rate limiting and budget counters."""
        ...

    @abstractmethod
    def ping(self) -> bool: ...
