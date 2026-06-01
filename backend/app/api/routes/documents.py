from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import Document
from app.models.chunk import Chunk
from app.schemas.document import ChunkOperationResponse, DocumentDetailRead, DocumentRead
from app.schemas.chunk import ChunkStatusResponse
from app.services.chunking import chunk_document
from app.services.embeddings import embed_document_chunks

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentDetailRead)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/chunk-status", response_model=ChunkStatusResponse)
def get_chunk_status(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()
    embedded_count = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .filter(Chunk.embedding.isnot(None))
        .count()
    )

    return ChunkStatusResponse(
        document_id=document_id,
        chunk_count=chunk_count,
        embedded_count=embedded_count,
        status=document.status,
    )


@router.post("/{document_id}/chunk", response_model=ChunkOperationResponse)
def chunk_document_endpoint(document_id: int, db: Session = Depends(get_db)):
    try:
        count = chunk_document(db, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChunkOperationResponse(status="ok", document_id=document_id, chunks_created=count)


@router.post("/{document_id}/embed", response_model=ChunkOperationResponse)
def embed_document_endpoint(document_id: int, db: Session = Depends(get_db)):
    try:
        count = embed_document_chunks(db, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {exc}") from exc
    return ChunkOperationResponse(status="ok", document_id=document_id, chunks_created=count)
