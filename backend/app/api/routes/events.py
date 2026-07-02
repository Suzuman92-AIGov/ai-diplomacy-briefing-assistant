from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.event import Event, EventDocument
from app.models.event_intelligence import EventBrief, EventSnapshot
from app.schemas.event import EventDetailRead, EventDocumentRead, EventRead, EventReclusterResponse
from app.schemas.event_intelligence import (
    EventBriefGenerateResponse,
    EventBriefRead,
    EventChangeRead,
    EventSnapshotCreateResponse,
    EventSnapshotRead,
)
from app.services.event_intelligence import (
    create_event_snapshot,
    generate_event_brief,
    get_event_change,
    get_latest_event_snapshot,
)
from app.services.events import assign_document_to_event, serialize_event, serialize_event_document

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
def list_events(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.last_seen_at.desc(), Event.created_at.desc()).all()
    return [serialize_event(db, event) for event in events]


@router.post("/{event_id}/snapshots", response_model=EventSnapshotCreateResponse)
def create_snapshot(event_id: int, force: bool = False, db: Session = Depends(get_db)):
    try:
        snapshot, reused = create_event_snapshot(db, event_id, force=force)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create event snapshot") from exc
    return EventSnapshotCreateResponse(status="ok", reused=reused, snapshot=snapshot)


@router.get("/{event_id}/snapshots", response_model=list[EventSnapshotRead])
def list_snapshots(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return (
        db.query(EventSnapshot)
        .filter(EventSnapshot.event_id == event_id)
        .order_by(EventSnapshot.created_at.desc(), EventSnapshot.id.desc())
        .all()
    )


@router.get("/{event_id}/snapshots/latest", response_model=EventSnapshotRead)
def get_latest_snapshot(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    snapshot = get_latest_event_snapshot(db, event_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="No event snapshot exists")
    return snapshot


@router.get("/{event_id}/changes", response_model=EventChangeRead)
def get_event_changes(event_id: int, db: Session = Depends(get_db)):
    try:
        return get_event_change(db, event_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message in {"Event not found", "No event snapshot exists"} else 400
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.post("/{event_id}/briefs/generate", response_model=EventBriefGenerateResponse)
def generate_event_brief_endpoint(event_id: int, force: bool = False, db: Session = Depends(get_db)):
    try:
        brief, change, reused = generate_event_brief(db, event_id, force=force)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not generate event brief") from exc
    return EventBriefGenerateResponse(status="ok", reused=reused, brief=brief, change=change)


@router.get("/{event_id}/briefs", response_model=list[EventBriefRead])
def list_event_briefs(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return (
        db.query(EventBrief)
        .filter(EventBrief.event_id == event_id)
        .order_by(EventBrief.created_at.desc(), EventBrief.id.desc())
        .all()
    )


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
