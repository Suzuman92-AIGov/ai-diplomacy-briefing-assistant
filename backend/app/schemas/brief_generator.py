from pydantic import BaseModel


class BriefGenerateRequest(BaseModel):
    topic: str
    audience: str = "public diplomacy and policy team"
    top_k: int = 6


class BriefGenerateResponse(BaseModel):
    title: str
    topic: str
    audience: str
    content: str
    answer_provider: str
    retrieval_provider: str
    brief_id: int | None = None
    sources: list[dict]
