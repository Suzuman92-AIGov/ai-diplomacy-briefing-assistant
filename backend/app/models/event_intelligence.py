from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventSnapshot(Base):
    __tablename__ = "event_snapshots"
    __table_args__ = (
        Index("ix_event_snapshots_event_id", "event_id"),
        Index("ix_event_snapshots_created_at", "created_at"),
        Index("ix_event_snapshots_snapshot_hash", "snapshot_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False, default="event_state")
    event_title: Mapped[str] = mapped_column(String(500), nullable=False)
    event_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_status: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    country_or_region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_count: Mapped[int] = mapped_column(nullable=False, default=0)
    distinct_source_count: Mapped[int] = mapped_column(nullable=False, default=0)
    distinct_publisher_count: Mapped[int] = mapped_column(nullable=False, default=0)
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    publisher_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    latest_evidence_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event")


class EventBrief(Base):
    __tablename__ = "event_briefs"
    __table_args__ = (
        Index("ix_event_briefs_event_id", "event_id"),
        Index("ix_event_briefs_snapshot_id", "snapshot_id"),
        Index("ix_event_briefs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("event_snapshots.id"), nullable=False)
    previous_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("event_snapshots.id"), nullable=True)
    brief_status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    what_happened: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    uncertainties: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    watch_next: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    change_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generation_method: Mapped[str] = mapped_column(String(50), nullable=False, default="deterministic")
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    event = relationship("Event")
    snapshot = relationship("EventSnapshot", foreign_keys=[snapshot_id])
    previous_snapshot = relationship("EventSnapshot", foreign_keys=[previous_snapshot_id])
