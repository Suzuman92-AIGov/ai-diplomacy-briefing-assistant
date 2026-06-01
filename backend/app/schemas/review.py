from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BriefReviewUpdate(BaseModel):
    review_status: str
    reviewer_notes: str | None = None
    reviewer: str = "demo_reviewer"


class BriefReviewResponse(BaseModel):
    id: int
    title: str
    review_status: str
    reviewer_notes: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BriefDetailResponse(BaseModel):
    id: int
    title: str
    brief_type: str
    query_or_topic: str | None = None
    content: str
    executive_summary: str | None = None
    sensitivity_level: str
    confidence_level: str
    review_status: str
    reviewer_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    sources: list[dict]
