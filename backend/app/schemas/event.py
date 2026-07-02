from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EventBase(BaseModel):
    id: int
    title: str
    normalized_title: str
    summary: str | None = None
    event_type: str
    status: str
    primary_language: str | None = None
    country_or_region: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventRead(EventBase):
    related_document_count: int = 0


class EventDocumentRead(BaseModel):
    event_id: int
    document_id: int
    document_title: str
    source_name: str | None = None
    publisher: str | None = None
    url: str
    published_date: date | None = None
    fetched_at: datetime
    relationship_type: str
    similarity_score: float | None = None
    clustering_method: str


class EventDetailRead(EventRead):
    related_documents: list[EventDocumentRead] = Field(default_factory=list)


class EventReclusterResponse(BaseModel):
    status: str
    document_id: int
    event_id: int
    clustering_method: str
    similarity_score: float | None = None


class EventBackfillProposal(BaseModel):
    document_id: int
    document_title: str
    action: str
    event_id: int | None = None
    event_title: str
    clustering_method: str
    similarity_score: float | None = None


class EventBackfillResponse(BaseModel):
    status: str
    dry_run: bool
    processed: int
    proposed_groups: list[EventBackfillProposal]
