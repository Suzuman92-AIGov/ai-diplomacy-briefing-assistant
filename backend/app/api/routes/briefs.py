from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.brief import Brief, BriefSource
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import Source
from app.schemas.brief import BriefRead
from app.schemas.review import BriefDetailResponse, BriefReviewResponse, BriefReviewUpdate
from app.services.audit import create_audit_log

router = APIRouter(prefix="/briefs", tags=["briefs"])

ALLOWED_REVIEW_STATUSES = {
    "draft",
    "reviewed",
    "approved",
    "rejected",
    "needs_senior_review",
}


@router.get("", response_model=list[BriefRead])
def list_briefs(db: Session = Depends(get_db)):
    return db.query(Brief).order_by(Brief.created_at.desc()).all()


@router.get("/{brief_id}", response_model=BriefDetailResponse)
def get_brief(brief_id: int, db: Session = Depends(get_db)):
    brief = db.query(Brief).filter(Brief.id == brief_id).first()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    source_rows = (
        db.query(BriefSource, Document, Chunk, Source)
        .outerjoin(Document, BriefSource.document_id == Document.id)
        .outerjoin(Chunk, BriefSource.chunk_id == Chunk.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .filter(BriefSource.brief_id == brief_id)
        .order_by(BriefSource.id.asc())
        .all()
    )

    sources = []
    for brief_source, document, chunk, source in source_rows:
        sources.append(
            {
                "citation_label": brief_source.citation_label,
                "document_id": document.id if document else None,
                "chunk_id": chunk.id if chunk else None,
                "title": document.title if document else None,
                "url": document.url if document else None,
                "source_name": source.name if source else None,
                "reliability_tier": source.reliability_tier if source else None,
                "excerpt": chunk.content[:700] if chunk and chunk.content else None,
            }
        )

    return BriefDetailResponse(
        id=brief.id,
        title=brief.title,
        brief_type=brief.brief_type,
        query_or_topic=brief.query_or_topic,
        content=brief.content,
        executive_summary=brief.executive_summary,
        sensitivity_level=brief.sensitivity_level,
        confidence_level=brief.confidence_level,
        review_status=brief.review_status,
        reviewer_notes=brief.reviewer_notes,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
        sources=sources,
    )


@router.patch("/{brief_id}/review", response_model=BriefReviewResponse)
def update_brief_review(
    brief_id: int,
    payload: BriefReviewUpdate,
    db: Session = Depends(get_db),
):
    brief = db.query(Brief).filter(Brief.id == brief_id).first()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")

    if payload.review_status not in ALLOWED_REVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review_status. Allowed: {sorted(ALLOWED_REVIEW_STATUSES)}",
        )

    previous_status = brief.review_status
    brief.review_status = payload.review_status
    brief.reviewer_notes = payload.reviewer_notes
    db.commit()
    db.refresh(brief)

    create_audit_log(
        db,
        action="update_brief_review",
        entity_type="brief",
        entity_id=str(brief.id),
        actor=payload.reviewer,
        details=f"Review status changed from {previous_status} to {payload.review_status}.",
    )

    return BriefReviewResponse(
        id=brief.id,
        title=brief.title,
        review_status=brief.review_status,
        reviewer_notes=brief.reviewer_notes,
        updated_at=brief.updated_at,
    )
