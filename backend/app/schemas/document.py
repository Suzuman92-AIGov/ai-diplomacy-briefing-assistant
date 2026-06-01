from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    id: int
    source_id: int | None = None
    title: str
    url: str
    published_date: date | None = None
    fetched_at: datetime
    language: str | None = None
    summary: str | None = None
    topic_tags: str | None = None
    sensitivity_level: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailRead(DocumentRead):
    cleaned_text: str | None = None


class ChunkOperationResponse(BaseModel):
    status: str
    document_id: int
    chunks_created: int
