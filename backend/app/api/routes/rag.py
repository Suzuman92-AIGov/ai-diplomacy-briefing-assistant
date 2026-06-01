from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rag import RagAnswerRequest, RagAnswerResponse
from app.services.rag import answer_question

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/answer", response_model=RagAnswerResponse)
def rag_answer(payload: RagAnswerRequest, db: Session = Depends(get_db)):
    try:
        result = answer_question(db, question=payload.question, top_k=payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG answer failed: {exc}") from exc

    return result
