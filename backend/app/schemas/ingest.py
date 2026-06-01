from pydantic import BaseModel, HttpUrl


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    source_id: int | None = None
    topic_tags: str | None = None
    sensitivity_level: str = "medium"
    language: str | None = None


class UrlIngestResponse(BaseModel):
    status: str
    document_id: int
    title: str
    url: str
    text_length: int
