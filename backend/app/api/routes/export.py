from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.export import export_brief_markdown

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/brief/{brief_id}/markdown")
def export_brief_as_markdown(brief_id: int, db: Session = Depends(get_db)):
    try:
        return export_brief_markdown(db, brief_id=brief_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc
