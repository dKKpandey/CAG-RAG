
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceChunk(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict = Field(default_factory=dict)


class UsageInfo(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    cache_hit: bool
    usage: UsageInfo


class IngestDocument(BaseModel):
    id: str | None = None
    text: str
    metadata: dict = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[IngestDocument]


class IngestResponse(BaseModel):
    ingested: int


class PreloadCacheResponse(BaseModel):
    cached_chars: int
    source_files: list[str]
    content_hash: str


class HealthResponse(BaseModel):
    status: str
    redis_ok: bool
    vector_store_ok: bool
