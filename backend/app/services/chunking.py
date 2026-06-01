from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.audit import create_audit_log


def estimate_token_count(text: str) -> int:
    # Rough approximation: English text is often around 4 characters per token.
    return max(1, len(text) // 4)


def chunk_text(text: str, *, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(0, end - overlap)

    return chunks


def chunk_document(
    db: Session,
    *,
    document_id: int,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> int:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document with id={document_id} does not exist.")

    if not document.cleaned_text:
        raise ValueError("Document has no cleaned_text to chunk.")

    existing_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()

    # Phase 5.1 safety behavior:
    # If chunks already exist, do NOT delete/recreate them.
    # Existing chunks may already be referenced by generated briefs through brief_sources.
    # Deleting them would break citation integrity and trigger foreign key violations.
    if existing_count > 0:
        create_audit_log(
            db,
            action="chunk_document_skipped_existing",
            entity_type="document",
            entity_id=str(document_id),
            details=f"Skipped chunking because {existing_count} chunks already exist.",
        )
        return existing_count

    chunks = chunk_text(document.cleaned_text, chunk_size=chunk_size, overlap=overlap)

    for index, content in enumerate(chunks):
        chunk = Chunk(
            document_id=document_id,
            chunk_index=index,
            content=content,
            token_count=estimate_token_count(content),
        )
        db.add(chunk)

    document.status = "chunked"
    db.commit()

    create_audit_log(
        db,
        action="chunk_document",
        entity_type="document",
        entity_id=str(document_id),
        details=f"Created {len(chunks)} chunks.",
    )

    return len(chunks)
