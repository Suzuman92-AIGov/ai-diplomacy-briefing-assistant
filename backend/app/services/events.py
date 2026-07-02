from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.event import Event, EventDocument
from app.models.source import Source

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "msclkid",
    "yclid",
}


@dataclass
class EventMatch:
    event: Event
    clustering_method: str
    similarity_score: float


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lowered_key = key.lower()
        if lowered_key.startswith("utm_") or lowered_key in TRACKING_QUERY_PARAMS:
            continue
        query_items.append((key, value))

    query = urlencode(sorted(query_items))
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    normalized = unicodedata.normalize("NFKC", title).lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def content_hash(text: str | None) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def title_similarity(left: str, right: str) -> float:
    normalized_left = normalize_title(left)
    normalized_right = normalize_title(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0

    sequence_score = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    jaccard_score = _token_jaccard(normalized_left, normalized_right)
    return max(sequence_score, jaccard_score)


def semantic_text_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0

    try:
        matrix = TfidfVectorizer(analyzer="char", ngram_range=(2, 5)).fit_transform(
            [normalized_left, normalized_right]
        )
    except ValueError:
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()
    tfidf_score = float(cosine_similarity(matrix[0], matrix[1])[0][0])
    sequence_score = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    return max(tfidf_score, sequence_score)


def document_seen_at(document: Document) -> datetime:
    if document.published_date:
        return datetime.combine(document.published_date, time.min)
    return document.fetched_at


def _event_document_link(db: Session, document_id: int) -> EventDocument | None:
    return (
        db.query(EventDocument)
        .filter(EventDocument.document_id == document_id)
        .filter(EventDocument.relationship_type == "primary")
        .first()
    )


def _first_linked_event_for_document(db: Session, document_id: int) -> Event | None:
    link = _event_document_link(db, document_id)
    return link.event if link else None


def _document_text_for_similarity(document: Document) -> str:
    return " ".join(
        item
        for item in [document.title, document.summary or "", document.topic_tags or ""]
        if item
    )


def _event_text_for_similarity(event: Event) -> str:
    return " ".join(item for item in [event.title, event.summary or ""] if item)


def _event_source_ids(event: Event) -> set[int]:
    return {
        link.document.source_id
        for link in event.documents
        if link.document.source_id is not None
    }


def _temporal_distance_days(document: Document, event: Event) -> int:
    seen_at = document_seen_at(document)
    if event.first_seen_at <= seen_at <= event.last_seen_at:
        return 0
    if seen_at < event.first_seen_at:
        delta = event.first_seen_at - seen_at
    else:
        delta = seen_at - event.last_seen_at
    return abs(delta.days)


def _is_temporally_compatible(document: Document, event: Event) -> bool:
    return _temporal_distance_days(document, event) <= settings.event_title_match_window_days


def _candidate_score(document: Document, event: Event, similarity_score: float) -> float:
    source_bonus = 0.03 if document.source_id and document.source_id in _event_source_ids(event) else 0.0
    recency_bonus = max(
        0.0,
        (settings.event_title_match_window_days - _temporal_distance_days(document, event))
        / max(settings.event_title_match_window_days, 1),
    ) * 0.02
    return similarity_score + source_bonus + recency_bonus


def find_duplicate_document(db: Session, document: Document) -> tuple[Document | None, str, float | None]:
    exact_url_match = (
        db.query(Document)
        .filter(Document.id != document.id)
        .filter(Document.url == document.url)
        .order_by(Document.created_at.asc())
        .first()
    )
    if exact_url_match:
        return exact_url_match, "exact_canonical_url", 1.0

    normalized_url = normalize_url(document.url)
    for candidate in db.query(Document).filter(Document.id != document.id).all():
        if normalize_url(candidate.url) == normalized_url:
            return candidate, "normalized_url", 1.0

    document_hash = content_hash(document.cleaned_text)
    if document_hash:
        for candidate in db.query(Document).filter(Document.id != document.id).all():
            if content_hash(candidate.cleaned_text) == document_hash:
                return candidate, "content_hash", 1.0

    return None, "", None


def find_event_candidate(db: Session, document: Document) -> EventMatch | None:
    duplicate_document, method, score = find_duplicate_document(db, document)
    if duplicate_document:
        event = _first_linked_event_for_document(db, duplicate_document.id)
        if event:
            return EventMatch(event=event, clustering_method=method, similarity_score=score or 1.0)

    best_title_match: EventMatch | None = None
    best_title_rank = 0.0
    for event in db.query(Event).all():
        if not _is_temporally_compatible(document, event):
            continue
        score = title_similarity(document.title, event.title)
        if score >= settings.event_near_duplicate_title_threshold:
            candidate_rank = _candidate_score(document, event, score)
            if best_title_match is None or candidate_rank > best_title_rank:
                best_title_rank = candidate_rank
                best_title_match = EventMatch(
                    event=event,
                    clustering_method="near_duplicate_title",
                    similarity_score=score,
                )
    if best_title_match:
        return best_title_match

    document_text = _document_text_for_similarity(document)
    best_semantic_match: EventMatch | None = None
    best_semantic_rank = 0.0
    for event in db.query(Event).all():
        if not _is_temporally_compatible(document, event):
            continue
        score = semantic_text_similarity(document_text, _event_text_for_similarity(event))
        if score >= settings.event_semantic_similarity_threshold:
            candidate_rank = _candidate_score(document, event, score)
            if best_semantic_match is None or candidate_rank > best_semantic_rank:
                best_semantic_rank = candidate_rank
                best_semantic_match = EventMatch(
                    event=event,
                    clustering_method="semantic_title_summary",
                    similarity_score=score,
                )
    return best_semantic_match


def _event_summary_from_document(document: Document) -> str | None:
    if document.summary:
        return document.summary
    if document.cleaned_text:
        return document.cleaned_text[:500]
    return None


def create_event_from_document(db: Session, document: Document) -> Event:
    normalized_title = normalize_title(document.title) or f"document {document.id}"
    seen_at = document_seen_at(document)
    source = document.source
    event = Event(
        title=document.title,
        normalized_title=normalized_title,
        summary=_event_summary_from_document(document),
        event_type="development",
        status="active",
        primary_language=document.language,
        country_or_region=source.country_or_institution if source else None,
        first_seen_at=seen_at,
        last_seen_at=seen_at,
    )
    db.add(event)
    db.flush()
    return event


def assign_document_to_event(db: Session, *, document_id: int) -> EventDocument:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError("Document not found")

    existing_link = _event_document_link(db, document_id)
    if existing_link:
        return existing_link

    match = find_event_candidate(db, document)
    if match:
        event = match.event
        clustering_method = match.clustering_method
        similarity_score = match.similarity_score
    else:
        event = create_event_from_document(db, document)
        clustering_method = "new_event"
        similarity_score = 1.0

    seen_at = document_seen_at(document)
    if seen_at < event.first_seen_at:
        event.first_seen_at = seen_at
    if seen_at > event.last_seen_at:
        event.last_seen_at = seen_at

    link = EventDocument(
        event_id=event.id,
        document_id=document.id,
        relationship_type="primary",
        similarity_score=similarity_score,
        clustering_method=clustering_method,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def serialize_event_document(link: EventDocument) -> dict:
    document = link.document
    source: Source | None = document.source
    return {
        "event_id": link.event_id,
        "document_id": document.id,
        "document_title": document.title,
        "source_name": source.name if source else None,
        "publisher": source.name if source else None,
        "url": document.url,
        "published_date": document.published_date,
        "fetched_at": document.fetched_at,
        "relationship_type": link.relationship_type,
        "similarity_score": link.similarity_score,
        "clustering_method": link.clustering_method,
    }


def event_document_count(db: Session, event_id: int) -> int:
    return db.query(EventDocument).filter(EventDocument.event_id == event_id).count()


def event_distinct_source_count(event: Event) -> int:
    source_names = {
        link.document.source.name.strip()
        for link in event.documents
        if link.document and link.document.source and link.document.source.name
    }
    return len(source_names)


def serialize_event(db: Session, event: Event, *, include_documents: bool = False) -> dict:
    distinct_source_count = event_distinct_source_count(event)
    payload = {
        "id": event.id,
        "title": event.title,
        "normalized_title": event.normalized_title,
        "summary": event.summary,
        "event_type": event.event_type,
        "status": event.status,
        "primary_language": event.primary_language,
        "country_or_region": event.country_or_region,
        "first_seen_at": event.first_seen_at,
        "last_seen_at": event.last_seen_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "related_document_count": event_document_count(db, event.id),
        "distinct_source_count": distinct_source_count,
        "distinct_publisher_count": distinct_source_count,
    }
    if include_documents:
        payload["related_documents"] = [
            serialize_event_document(link)
            for link in sorted(event.documents, key=lambda item: item.created_at)
        ]
    return payload


def backfill_documents_to_events(db: Session, *, dry_run: bool = True) -> dict:
    proposals = []
    documents = db.query(Document).order_by(Document.created_at.asc()).all()

    for document in documents:
        existing_link = _event_document_link(db, document.id)
        if existing_link:
            proposals.append(
                {
                    "document_id": document.id,
                    "document_title": document.title,
                    "action": "already_assigned",
                    "event_id": existing_link.event_id,
                    "event_title": existing_link.event.title,
                    "clustering_method": existing_link.clustering_method,
                    "similarity_score": existing_link.similarity_score,
                }
            )
            continue

        match = find_event_candidate(db, document)
        if dry_run:
            proposals.append(
                {
                    "document_id": document.id,
                    "document_title": document.title,
                    "action": "assign_existing_event" if match else "create_event",
                    "event_id": match.event.id if match else None,
                    "event_title": match.event.title if match else document.title,
                    "clustering_method": match.clustering_method if match else "new_event",
                    "similarity_score": match.similarity_score if match else 1.0,
                }
            )
            continue

        link = assign_document_to_event(db, document_id=document.id)
        proposals.append(
            {
                "document_id": document.id,
                "document_title": document.title,
                "action": "assigned",
                "event_id": link.event_id,
                "event_title": link.event.title,
                "clustering_method": link.clustering_method,
                "similarity_score": link.similarity_score,
            }
        )

    return {
        "status": "ok",
        "dry_run": dry_run,
        "processed": len(documents),
        "proposed_groups": proposals,
    }
