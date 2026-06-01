from datetime import date
from pydantic import BaseModel


class RagAnswerRequest(BaseModel):
    question: str
    top_k: int = 5


class RagCitation(BaseModel):
    citation_id: str
    chunk_id: int
    document_id: int
    title: str
    url: str
    source_name: str | None = None
    reliability_tier: str | None = None
    published_date: date | None = None
    excerpt: str


class RagAnswerResponse(BaseModel):
    question: str
    answer: str
    answer_provider: str
    retrieval_provider: str
    citations: list[RagCitation]
