from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SourceBase(BaseModel):
    name: str
    base_url: str | None = None
    source_type: str = "other"
    reliability_tier: str = "medium"
    country_or_institution: str | None = None
    notes: str | None = None
    is_active: bool = True


class SourceCreate(SourceBase):
    pass


class SourceRead(SourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
