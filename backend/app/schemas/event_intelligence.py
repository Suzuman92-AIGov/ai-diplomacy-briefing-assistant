from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventSnapshotRead(BaseModel):
    id: int
    event_id: int
    snapshot_type: str
    event_title: str
    event_summary: str | None = None
    event_status: str
    event_type: str
    country_or_region: str | None = None
    primary_language: str | None = None
    document_count: int
    distinct_source_count: int
    distinct_publisher_count: int
    document_ids: list[int] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    publisher_names: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    latest_evidence_at: datetime | None = None
    snapshot_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventSnapshotCreateResponse(BaseModel):
    status: str
    reused: bool
    snapshot: EventSnapshotRead


class EventChangeRead(BaseModel):
    has_changes: bool
    change_level: str
    is_initial_baseline: bool = False
    new_document_ids: list[int] = Field(default_factory=list)
    removed_document_ids: list[int] = Field(default_factory=list)
    new_sources: list[str] = Field(default_factory=list)
    removed_sources: list[str] = Field(default_factory=list)
    new_publishers: list[str] = Field(default_factory=list)
    removed_publishers: list[str] = Field(default_factory=list)
    document_count_delta: int = 0
    source_count_delta: int = 0
    publisher_count_delta: int = 0
    metadata_changes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    latest_evidence_at_changed: bool = False
    summary_changed: bool = False
    deterministic_change_summary: str
    previous_snapshot_id: int | None = None
    current_snapshot_id: int | None = None


class EventBriefRead(BaseModel):
    id: int
    event_id: int
    snapshot_id: int
    previous_snapshot_id: int | None = None
    brief_status: str
    reviewer_notes: str | None = None
    headline: str
    what_happened: str | None = None
    what_changed: str | None = None
    why_it_matters: str | None = None
    confirmed_points: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    watch_next: list[str] = Field(default_factory=list)
    evidence_document_ids: list[int] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    change_summary: dict[str, Any] = Field(default_factory=dict)
    generation_method: str
    model_name: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventBriefGenerateResponse(BaseModel):
    status: str
    reused: bool
    brief: EventBriefRead
    change: EventChangeRead


class EventBriefReviewUpdate(BaseModel):
    brief_status: str
    reviewer_notes: str | None = None
    reviewer: str = "demo_reviewer"


class EventBriefReviewResponse(BaseModel):
    id: int
    event_id: int
    brief_status: str
    reviewer_notes: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
