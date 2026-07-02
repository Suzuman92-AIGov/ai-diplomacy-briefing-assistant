from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.event_intelligence import EventBrief
from app.schemas.event_intelligence import EventBriefRead, EventBriefReviewResponse, EventBriefReviewUpdate
from app.services.event_intelligence import update_event_brief_review

router = APIRouter(prefix="/event-briefs", tags=["event briefs"])


@router.get("/{brief_id}", response_model=EventBriefRead)
def get_event_brief(brief_id: int, db: Session = Depends(get_db)):
    brief = db.query(EventBrief).filter(EventBrief.id == brief_id).first()
    if not brief:
        raise HTTPException(status_code=404, detail="Event brief not found")
    return brief


@router.patch("/{brief_id}/review", response_model=EventBriefReviewResponse)
def review_event_brief(
    brief_id: int,
    payload: EventBriefReviewUpdate,
    db: Session = Depends(get_db),
):
    try:
        brief = update_event_brief_review(
            db,
            brief_id,
            brief_status=payload.brief_status,
            reviewer_notes=payload.reviewer_notes,
            reviewer=payload.reviewer,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Event brief not found" else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update event brief review") from exc

    return EventBriefReviewResponse(
        id=brief.id,
        event_id=brief.event_id,
        brief_status=brief.brief_status,
        reviewer_notes=brief.reviewer_notes,
        updated_at=brief.updated_at,
    )
