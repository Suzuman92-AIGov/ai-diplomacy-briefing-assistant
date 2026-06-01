from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.audit import create_audit_log


def get_openai_client() -> OpenAI:
    if not settings.openai_api_key or settings.openai_api_key == "your_api_key_here":
        raise ValueError("OPENAI_API_KEY is missing. Add it to the project .env file.")
    return OpenAI(api_key=settings.openai_api_key)


def embed_text_openai(text: str) -> list[float]:
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )
    return response.data[0].embedding


def embed_text_local_placeholder(text: str) -> list[float]:
    """
    Local demo placeholder vector.

    In local mode, real retrieval uses TF-IDF directly over chunk text.
    This deterministic vector simply allows the app to mark chunks as
    prepared/searchable without calling an external API.
    """
    import hashlib
    import random

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    seed = int(digest[:16], 16)
    rng = random.Random(seed)
    return [rng.uniform(-0.01, 0.01) for _ in range(1536)]


def embed_text(text: str) -> list[float]:
    if settings.embedding_provider.lower() == "local":
        return embed_text_local_placeholder(text)
    return embed_text_openai(text)


def embed_document_chunks(db: Session, *, document_id: int) -> int:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document with id={document_id} does not exist.")

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index.asc())
        .all()
    )

    if not chunks:
        raise ValueError("Document has no chunks. Run chunking first.")

    count = 0
    for chunk in chunks:
        chunk.embedding = embed_text(chunk.content)
        count += 1

    document.status = "embedded_local" if settings.embedding_provider.lower() == "local" else "embedded"
    db.commit()

    create_audit_log(
        db,
        action="embed_document",
        entity_type="document",
        entity_id=str(document_id),
        details=f"Prepared {count} chunks using provider={settings.embedding_provider}.",
    )

    return count
