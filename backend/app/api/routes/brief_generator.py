from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.brief_generator import BriefGenerateRequest, BriefGenerateResponse
from app.services.brief_generator import generate_policy_brief

router = APIRouter(prefix="/brief-generator", tags=["brief generator"])


@router.post("/generate", response_model=BriefGenerateResponse)
def generate_brief(payload: BriefGenerateRequest, db: Session = Depends(get_db)):
    try:
        result = generate_policy_brief(
            db,
            topic=payload.topic,
            audience=payload.audience,
            top_k=payload.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Brief generation failed: {exc}") from exc

    return result
