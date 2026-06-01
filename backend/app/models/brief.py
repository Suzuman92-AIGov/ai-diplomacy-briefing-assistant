from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    brief_type: Mapped[str] = mapped_column(String(50), nullable=False, default="topic")
    query_or_topic: Mapped[str | None] = mapped_column(Text, nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    sensitivity_level: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    confidence_level: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    sources = relationship("BriefSource", back_populates="brief", cascade="all, delete-orphan")


class BriefSource(Base):
    __tablename__ = "brief_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id"), nullable=True, index=True)

    citation_label: Mapped[str] = mapped_column(String(100), nullable=False)

    brief = relationship("Brief", back_populates="sources")
    document = relationship("Document", back_populates="brief_sources")
    chunk = relationship("Chunk", back_populates="brief_sources")
