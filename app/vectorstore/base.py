from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict]) -> None: ...

    @abstractmethod
    def similarity_search(self, query: str, k: int) -> list[RetrievedChunk]: ...

    @abstractmethod
    def ping(self) -> bool: ...
