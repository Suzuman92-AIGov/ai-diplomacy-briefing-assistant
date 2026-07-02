from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="development")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country_or_region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    documents = relationship("EventDocument", back_populates="event", cascade="all, delete-orphan")


class EventDocument(Base):
    __tablename__ = "event_documents"
    __table_args__ = (
        UniqueConstraint("event_id", "document_id", name="uq_event_documents_event_document"),
        Index(
            "uq_event_documents_primary_document",
            "document_id",
            unique=True,
            postgresql_where=text("relationship_type = 'primary'"),
            sqlite_where=text("relationship_type = 'primary'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, default="primary")
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clustering_method: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="documents")
    document = relationship("Document", back_populates="event_links")
