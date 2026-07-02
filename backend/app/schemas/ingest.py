from pydantic import BaseModel, Field, HttpUrl


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    source_id: int | None = Field(default=None, gt=0)
    topic_tags: str | None = None
    sensitivity_level: str = "medium"
    language: str | None = None


class UrlIngestResponse(BaseModel):
    status: str
    document_id: int
    title: str
    url: str
    text_length: int
