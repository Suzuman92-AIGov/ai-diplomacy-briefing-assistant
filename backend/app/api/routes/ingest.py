from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ingest import UrlIngestRequest, UrlIngestResponse
from app.services.ingestion import ingest_url

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/url", response_model=UrlIngestResponse)
def ingest_public_url(payload: UrlIngestRequest, db: Session = Depends(get_db)):
    try:
        document = ingest_url(
            db,
            url=str(payload.url),
            source_id=payload.source_id,
            topic_tags=payload.topic_tags,
            sensitivity_level=payload.sensitivity_level,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return UrlIngestResponse(
        status="ok",
        document_id=document.id,
        title=document.title,
        url=document.url,
        text_length=len(document.cleaned_text or ""),
    )
