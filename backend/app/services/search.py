from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import Source
from app.services.embeddings import embed_text


def _search_openai_pgvector(db: Session, *, query: str, top_k: int = 6):
    query_embedding = embed_text(query)
    distance_expr = Chunk.embedding.l2_distance(query_embedding).label("distance")

    rows = (
        db.query(Chunk, Document, Source, distance_expr)
        .join(Document, Chunk.document_id == Document.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .filter(Chunk.embedding.isnot(None))
        .order_by(distance_expr.asc())
        .limit(top_k)
        .all()
    )

    results = []
    for chunk, document, source, distance in rows:
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "title": document.title,
                "url": document.url,
                "source_name": source.name if source else None,
                "source_type": source.source_type if source else None,
                "reliability_tier": source.reliability_tier if source else None,
                "published_date": document.published_date,
                "content": chunk.content,
                "distance": float(distance) if distance is not None else None,
            }
        )
    return results


def _search_local_tfidf(db: Session, *, query: str, top_k: int = 6):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    rows = (
        db.query(Chunk, Document, Source)
        .join(Document, Chunk.document_id == Document.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .order_by(Chunk.id.asc())
        .all()
    )

    if not rows:
        return []

    texts = [chunk.content for chunk, _, _ in rows]
    corpus = texts + [query]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
    )
    matrix = vectorizer.fit_transform(corpus)
    chunk_matrix = matrix[:-1]
    query_vector = matrix[-1]

    similarities = cosine_similarity(query_vector, chunk_matrix).flatten()
    ranked_indices = similarities.argsort()[::-1][:top_k]

    results = []
    for idx in ranked_indices:
        chunk, document, source = rows[int(idx)]
        similarity = float(similarities[int(idx)])
        distance = 1.0 - similarity

        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "title": document.title,
                "url": document.url,
                "source_name": source.name if source else None,
                "source_type": source.source_type if source else None,
                "reliability_tier": source.reliability_tier if source else None,
                "published_date": document.published_date,
                "content": chunk.content,
                "distance": distance,
            }
        )

    return results


def semantic_search(db: Session, *, query: str, top_k: int = 6):
    if settings.embedding_provider.lower() == "local":
        return _search_local_tfidf(db, query=query, top_k=top_k)
    return _search_openai_pgvector(db, query=query, top_k=top_k)
