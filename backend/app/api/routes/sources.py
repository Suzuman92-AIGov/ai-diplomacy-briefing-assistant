import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.source import Source
from app.schemas.source import SourceCreate, SourceRead

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)


def normalize_source_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def find_source_by_normalized_name(db: Session, normalized_name: str) -> Source | None:
    return (
        db.query(Source)
        .filter(func.lower(Source.name) == normalized_name.lower())
        .first()
    )


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    normalized_name = normalize_source_name(values["name"])
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Source name is required.")

    existing = find_source_by_normalized_name(db, normalized_name)
    if existing:
        response.status_code = status.HTTP_200_OK
        logger.info(
            "source_create_returned_existing",
            extra={"source_id": existing.id, "source_name": existing.name},
        )
        return existing

    values["name"] = normalized_name
    source = Source(**values)
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = find_source_by_normalized_name(db, normalized_name)
        if existing:
            response.status_code = status.HTTP_200_OK
            logger.info(
                "source_create_race_returned_existing",
                extra={"source_id": existing.id, "source_name": existing.name},
            )
            return existing
        logger.warning(
            "source_create_integrity_error_without_existing_source",
            extra={"source_name": normalized_name},
        )
        raise HTTPException(
            status_code=409,
            detail="Source could not be created because of a conflicting record.",
        ) from exc
    db.refresh(source)
    logger.info(
        "source_created",
        extra={"source_id": source.id, "source_name": source.name},
    )
    return source


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).order_by(Source.created_at.desc()).all()
