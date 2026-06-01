from datetime import date
from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    url: str
    source_name: str | None = None
    source_type: str | None = None
    reliability_tier: str | None = None
    published_date: date | None = None
    content: str
    distance: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
