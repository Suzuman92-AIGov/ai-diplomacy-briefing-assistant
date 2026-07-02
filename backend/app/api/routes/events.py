from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.event import Event, EventDocument
from app.schemas.event import EventDetailRead, EventDocumentRead, EventRead, EventReclusterResponse
from app.services.events import assign_document_to_event, serialize_event, serialize_event_document

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
def list_events(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.last_seen_at.desc(), Event.created_at.desc()).all()
    return [serialize_event(db, event) for event in events]


@router.get("/{event_id}", response_model=EventDetailRead)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_event(db, event, include_documents=True)


@router.get("/{event_id}/documents", response_model=list[EventDocumentRead])
def list_event_documents(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    links = (
        db.query(EventDocument)
        .filter(EventDocument.event_id == event_id)
        .order_by(EventDocument.created_at.asc())
        .all()
    )
    return [serialize_event_document(link) for link in links]


@router.post("/recluster/{document_id}", response_model=EventReclusterResponse)
def recluster_document(document_id: int, db: Session = Depends(get_db)):
    try:
        link = assign_document_to_event(db, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return EventReclusterResponse(
        status="ok",
        document_id=document_id,
        event_id=link.event_id,
        clustering_method=link.clustering_method,
        similarity_score=link.similarity_score,
    )
