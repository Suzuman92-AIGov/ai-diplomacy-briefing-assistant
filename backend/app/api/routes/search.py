from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.schemas.search import SearchResponse
from app.services.search import semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(query: str = Query(..., min_length=3), top_k: int = Query(default=None, ge=1, le=20), db: Session = Depends(get_db)):
    try:
        results = semantic_search(db, query=query, top_k=top_k or settings.default_top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc
    return SearchResponse(query=query, results=results)
