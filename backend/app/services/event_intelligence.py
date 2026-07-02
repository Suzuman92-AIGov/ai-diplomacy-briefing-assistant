from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event, EventDocument
from app.models.event_intelligence import EventBrief, EventSnapshot
from app.services.audit import create_audit_log
from app.services.events import document_seen_at

PROMPT_VERSION = "event_brief_v1"
ALLOWED_EVENT_BRIEF_STATUSES = {"draft", "reviewed", "approved", "rejected"}


def _shorten(text: str | None, max_chars: int = 700) -> str | None:
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _snapshot_hash_payload(snapshot_data: dict) -> dict:
    return {
        "event_title": snapshot_data["event_title"],
        "event_summary": snapshot_data.get("event_summary"),
        "event_status": snapshot_data["event_status"],
        "event_type": snapshot_data["event_type"],
        "country_or_region": snapshot_data.get("country_or_region"),
        "primary_language": snapshot_data.get("primary_language"),
        "document_ids": snapshot_data["document_ids"],
        "source_names": snapshot_data["source_names"],
        "publisher_names": snapshot_data["publisher_names"],
        "evidence_items": snapshot_data["evidence_items"],
        "latest_evidence_at": snapshot_data.get("latest_evidence_at"),
    }


def calculate_snapshot_hash(snapshot_data: dict) -> str:
    import hashlib

    canonical = json.dumps(
        _json_ready(_snapshot_hash_payload(snapshot_data)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_or_raise(db: Session, event_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise ValueError("Event not found")
    return event


def _source_name(link: EventDocument) -> str | None:
    if link.document and link.document.source and link.document.source.name:
        return link.document.source.name.strip()
    return None


def _evidence_excerpt(document) -> str | None:
    return _shorten(document.summary or document.cleaned_text, max_chars=500)


def build_event_snapshot(db: Session, event_id: int) -> dict:
    event = _event_or_raise(db, event_id)
    links = (
        db.query(EventDocument)
        .filter(EventDocument.event_id == event_id)
        .order_by(EventDocument.document_id.asc(), EventDocument.id.asc())
        .all()
    )

    evidence_items = []
    latest_evidence_at = None
    for link in links:
        document = link.document
        source_name = _source_name(link)
        seen_at = document_seen_at(document)
        if latest_evidence_at is None or seen_at > latest_evidence_at:
            latest_evidence_at = seen_at
        evidence_items.append(
            {
                "document_id": document.id,
                "title": document.title,
                "source_name": source_name,
                "publisher": source_name,
                "url": document.url,
                "published_date": document.published_date.isoformat() if document.published_date else None,
                "fetched_at": document.fetched_at.isoformat() if document.fetched_at else None,
                "relationship_type": link.relationship_type,
                "clustering_method": link.clustering_method,
                "similarity_score": link.similarity_score,
                "excerpt": _evidence_excerpt(document),
            }
        )

    document_ids = sorted(item["document_id"] for item in evidence_items)
    source_names = sorted({item["source_name"] for item in evidence_items if item.get("source_name")})
    publisher_names = sorted({item["publisher"] for item in evidence_items if item.get("publisher")})
    snapshot_data = {
        "event_id": event.id,
        "snapshot_type": "event_state",
        "event_title": event.title,
        "event_summary": event.summary,
        "event_status": event.status,
        "event_type": event.event_type,
        "country_or_region": event.country_or_region,
        "primary_language": event.primary_language,
        "document_count": len(document_ids),
        "distinct_source_count": len(source_names),
        "distinct_publisher_count": len(publisher_names),
        "document_ids": document_ids,
        "source_names": source_names,
        "publisher_names": publisher_names,
        "evidence_items": evidence_items,
        "latest_evidence_at": latest_evidence_at or event.last_seen_at,
    }
    snapshot_data["snapshot_hash"] = calculate_snapshot_hash(snapshot_data)
    return snapshot_data


def get_latest_event_snapshot(db: Session, event_id: int) -> EventSnapshot | None:
    return (
        db.query(EventSnapshot)
        .filter(EventSnapshot.event_id == event_id)
        .order_by(EventSnapshot.created_at.desc(), EventSnapshot.id.desc())
        .first()
    )


def get_previous_event_snapshot(
    db: Session,
    event_id: int,
    *,
    before_snapshot_id: int | None = None,
) -> EventSnapshot | None:
    query = db.query(EventSnapshot).filter(EventSnapshot.event_id == event_id)
    if before_snapshot_id is not None:
        current = db.query(EventSnapshot).filter(EventSnapshot.id == before_snapshot_id).first()
        if current:
            query = query.filter(EventSnapshot.id != current.id).filter(
                EventSnapshot.created_at <= current.created_at
            )
    return query.order_by(EventSnapshot.created_at.desc(), EventSnapshot.id.desc()).first()


def create_event_snapshot(db: Session, event_id: int, *, force: bool = False) -> tuple[EventSnapshot, bool]:
    latest = get_latest_event_snapshot(db, event_id)
    snapshot_data = build_event_snapshot(db, event_id)

    if latest and latest.snapshot_hash == snapshot_data["snapshot_hash"] and not force:
        create_audit_log(
            db,
            action="reuse_event_snapshot",
            entity_type="event_snapshot",
            entity_id=str(latest.id),
            details=f"Reused unchanged snapshot for event {event_id}.",
        )
        return latest, True

    snapshot_type = "baseline" if latest is None else "event_state"
    if force and latest and latest.snapshot_hash == snapshot_data["snapshot_hash"]:
        snapshot_type = "forced"

    snapshot = EventSnapshot(
        event_id=event_id,
        snapshot_type=snapshot_type,
        event_title=snapshot_data["event_title"],
        event_summary=snapshot_data["event_summary"],
        event_status=snapshot_data["event_status"],
        event_type=snapshot_data["event_type"],
        country_or_region=snapshot_data["country_or_region"],
        primary_language=snapshot_data["primary_language"],
        document_count=snapshot_data["document_count"],
        distinct_source_count=snapshot_data["distinct_source_count"],
        distinct_publisher_count=snapshot_data["distinct_publisher_count"],
        document_ids=snapshot_data["document_ids"],
        source_names=snapshot_data["source_names"],
        publisher_names=snapshot_data["publisher_names"],
        evidence_items=snapshot_data["evidence_items"],
        latest_evidence_at=snapshot_data["latest_evidence_at"],
        snapshot_hash=snapshot_data["snapshot_hash"],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    create_audit_log(
        db,
        action="create_event_snapshot",
        entity_type="event_snapshot",
        entity_id=str(snapshot.id),
        details=f"Created {snapshot.snapshot_type} snapshot for event {event_id}.",
    )
    return snapshot, False


def _snapshot_dict(snapshot: EventSnapshot | None) -> dict | None:
    if snapshot is None:
        return None
    return {
        "id": snapshot.id,
        "snapshot_hash": snapshot.snapshot_hash,
        "event_title": snapshot.event_title,
        "event_summary": snapshot.event_summary,
        "event_status": snapshot.event_status,
        "event_type": snapshot.event_type,
        "country_or_region": snapshot.country_or_region,
        "primary_language": snapshot.primary_language,
        "document_count": snapshot.document_count,
        "distinct_source_count": snapshot.distinct_source_count,
        "distinct_publisher_count": snapshot.distinct_publisher_count,
        "document_ids": snapshot.document_ids or [],
        "source_names": snapshot.source_names or [],
        "publisher_names": snapshot.publisher_names or [],
        "latest_evidence_at": snapshot.latest_evidence_at,
    }


def _metadata_changes(previous: dict, current: dict) -> dict:
    changes = {}
    for field in [
        "event_title",
        "event_status",
        "event_type",
        "country_or_region",
        "primary_language",
    ]:
        if previous.get(field) != current.get(field):
            changes[field] = {"previous": previous.get(field), "current": current.get(field)}
    return changes


def _list_delta(previous_values: list, current_values: list) -> tuple[list, list]:
    previous_set = set(previous_values or [])
    current_set = set(current_values or [])
    return sorted(current_set - previous_set), sorted(previous_set - current_set)


def compare_event_snapshots(
    previous_snapshot: EventSnapshot | None,
    current_snapshot: EventSnapshot,
) -> dict:
    current = _snapshot_dict(current_snapshot)
    previous = _snapshot_dict(previous_snapshot)

    if previous is None:
        return {
            "has_changes": False,
            "change_level": "none",
            "is_initial_baseline": True,
            "new_document_ids": [],
            "removed_document_ids": [],
            "new_sources": [],
            "removed_sources": [],
            "new_publishers": [],
            "removed_publishers": [],
            "document_count_delta": 0,
            "source_count_delta": 0,
            "publisher_count_delta": 0,
            "metadata_changes": {},
            "latest_evidence_at_changed": False,
            "summary_changed": False,
            "deterministic_change_summary": "Initial event baseline - no previous snapshot is available for comparison.",
            "previous_snapshot_id": None,
            "current_snapshot_id": current_snapshot.id,
        }

    if previous["snapshot_hash"] == current["snapshot_hash"]:
        return {
            "has_changes": False,
            "change_level": "none",
            "is_initial_baseline": False,
            "new_document_ids": [],
            "removed_document_ids": [],
            "new_sources": [],
            "removed_sources": [],
            "new_publishers": [],
            "removed_publishers": [],
            "document_count_delta": 0,
            "source_count_delta": 0,
            "publisher_count_delta": 0,
            "metadata_changes": {},
            "latest_evidence_at_changed": False,
            "summary_changed": False,
            "deterministic_change_summary": "No meaningful change detected since the previous snapshot.",
            "previous_snapshot_id": previous_snapshot.id,
            "current_snapshot_id": current_snapshot.id,
        }

    new_document_ids, removed_document_ids = _list_delta(previous["document_ids"], current["document_ids"])
    new_sources, removed_sources = _list_delta(previous["source_names"], current["source_names"])
    new_publishers, removed_publishers = _list_delta(previous["publisher_names"], current["publisher_names"])
    metadata_changes = _metadata_changes(previous, current)
    summary_changed = previous.get("event_summary") != current.get("event_summary")
    latest_changed = previous.get("latest_evidence_at") != current.get("latest_evidence_at")

    document_count_delta = current["document_count"] - previous["document_count"]
    source_count_delta = current["distinct_source_count"] - previous["distinct_source_count"]
    publisher_count_delta = current["distinct_publisher_count"] - previous["distinct_publisher_count"]

    if (
        len(new_sources) + len(new_publishers) >= 3
        and (metadata_changes or summary_changed or len(new_document_ids) >= 3)
    ):
        change_level = "major"
    elif metadata_changes or summary_changed or new_sources or new_publishers or len(new_document_ids) >= 3:
        change_level = "meaningful"
    elif new_document_ids or removed_document_ids or latest_changed:
        change_level = "minor"
    else:
        change_level = "none"

    parts = []
    if new_document_ids:
        parts.append(f"{len(new_document_ids)} new document(s)")
    if removed_document_ids:
        parts.append(f"{len(removed_document_ids)} removed document relationship(s)")
    if new_publishers:
        parts.append(f"{len(new_publishers)} newly represented publisher(s)")
    if new_sources:
        parts.append(f"{len(new_sources)} newly represented source(s)")
    if metadata_changes:
        parts.append(f"{len(metadata_changes)} metadata field(s) changed")
    if summary_changed:
        parts.append("event summary changed")
    if latest_changed:
        parts.append("latest evidence date changed")

    summary = "; ".join(parts) if parts else "No meaningful change detected since the previous snapshot."
    return {
        "has_changes": change_level != "none",
        "change_level": change_level,
        "is_initial_baseline": False,
        "new_document_ids": new_document_ids,
        "removed_document_ids": removed_document_ids,
        "new_sources": new_sources,
        "removed_sources": removed_sources,
        "new_publishers": new_publishers,
        "removed_publishers": removed_publishers,
        "document_count_delta": document_count_delta,
        "source_count_delta": source_count_delta,
        "publisher_count_delta": publisher_count_delta,
        "metadata_changes": metadata_changes,
        "latest_evidence_at_changed": latest_changed,
        "summary_changed": summary_changed,
        "deterministic_change_summary": summary,
        "previous_snapshot_id": previous_snapshot.id,
        "current_snapshot_id": current_snapshot.id,
    }


def get_event_change(db: Session, event_id: int) -> dict:
    _event_or_raise(db, event_id)
    current = get_latest_event_snapshot(db, event_id)
    if not current:
        raise ValueError("No event snapshot exists")
    previous = get_previous_event_snapshot(db, event_id, before_snapshot_id=current.id)
    return compare_event_snapshots(previous, current)


def _format_list(items: list[str], fallback: str) -> str:
    return ", ".join(items) if items else fallback


def _deterministic_brief_sections(snapshot: EventSnapshot, previous: EventSnapshot | None, change: dict) -> dict:
    evidence_count = len(snapshot.document_ids or [])
    publisher_count = len(snapshot.publisher_names or [])
    source_text = _format_list(snapshot.publisher_names or snapshot.source_names or [], "no registered publisher")
    headline = snapshot.event_title
    what_happened = (
        f"{snapshot.event_title} is represented by {evidence_count} related document(s) "
        f"from {publisher_count} distinct publisher(s): {source_text}."
    )
    if change.get("is_initial_baseline") or previous is None:
        what_changed = "Initial event baseline - no previous snapshot is available for comparison."
    elif change["change_level"] == "none":
        what_changed = "No meaningful change detected since the previous snapshot."
    else:
        what_changed = change["deterministic_change_summary"]

    why_it_matters = (
        "This event may matter for briefing workflows because changes in source coverage, event metadata, "
        "or evidence timing can affect how analysts prioritize review. Treat this as analysis guidance, not a policy claim."
    )

    confirmed_points = [
        f"Event status is {snapshot.event_status}.",
        f"Snapshot contains {evidence_count} evidence document(s).",
        f"Snapshot represents {publisher_count} publisher(s).",
    ]
    if snapshot.latest_evidence_at:
        confirmed_points.append(f"Latest evidence timestamp is {snapshot.latest_evidence_at.isoformat()}.")
    if change.get("new_document_ids"):
        confirmed_points.append(f"New evidence document IDs: {change['new_document_ids']}.")
    if change.get("new_publishers"):
        confirmed_points.append(f"Newly represented publishers: {change['new_publishers']}.")

    uncertainties = []
    if previous is None:
        uncertainties.append("No previous snapshot is available, so trend direction cannot be assessed yet.")
    if publisher_count <= 1:
        uncertainties.append("Only one publisher or source is represented in this snapshot.")
    if not snapshot.event_summary:
        uncertainties.append("No event-level summary is available from the backend event record.")
    if change["change_level"] == "none" and not change.get("is_initial_baseline"):
        uncertainties.append("No meaningful change was detected by deterministic comparison.")

    watch_next = [
        "Monitor whether additional documents are assigned to this event.",
        "Review any newly represented sources before using the event in external messaging.",
        "Check original document URLs before relying on analytical interpretation.",
    ]

    return {
        "headline": headline,
        "what_happened": what_happened,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "confirmed_points": confirmed_points,
        "uncertainties": uncertainties,
        "watch_next": watch_next,
    }


def _openai_event_brief_sections(snapshot: EventSnapshot, previous: EventSnapshot | None, change: dict) -> dict:
    if not settings.openai_api_key or settings.openai_api_key == "your_api_key_here":
        raise ValueError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=settings.openai_api_key)
    evidence_blocks = []
    for item in (snapshot.evidence_items or [])[:8]:
        evidence_blocks.append(
            {
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "publisher": item.get("publisher") or item.get("source_name"),
                "url": item.get("url"),
                "published_date": item.get("published_date"),
                "excerpt": _shorten(item.get("excerpt"), max_chars=450),
            }
        )

    prompt_payload = {
        "event": {
            "title": snapshot.event_title,
            "summary": snapshot.event_summary,
            "status": snapshot.event_status,
            "type": snapshot.event_type,
            "country_or_region": snapshot.country_or_region,
            "primary_language": snapshot.primary_language,
        },
        "previous_snapshot_id": previous.id if previous else None,
        "change": change,
        "evidence": evidence_blocks,
    }
    prompt = f"""
You are an evidence-first event briefing assistant.

Write a concise event brief using only this JSON data. Do not add facts not supported by the evidence.
Return only valid JSON with keys:
headline, what_happened, what_changed, why_it_matters, confirmed_points, uncertainties, watch_next.
The list fields must be arrays of short strings.

Data:
{json.dumps(prompt_payload, ensure_ascii=False, default=str)}
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": "You generate source-grounded event intelligence briefs."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    parsed = json.loads(content)
    required = {
        "headline",
        "what_happened",
        "what_changed",
        "why_it_matters",
        "confirmed_points",
        "uncertainties",
        "watch_next",
    }
    if not isinstance(parsed, dict) or required - set(parsed):
        raise ValueError("LLM response missing required fields.")
    for field in ["confirmed_points", "uncertainties", "watch_next"]:
        if not isinstance(parsed[field], list):
            raise ValueError("LLM response list field is malformed.")
    return parsed


def _existing_event_brief_for_snapshot(db: Session, snapshot_id: int) -> EventBrief | None:
    return (
        db.query(EventBrief)
        .filter(EventBrief.snapshot_id == snapshot_id)
        .order_by(EventBrief.created_at.desc(), EventBrief.id.desc())
        .first()
    )


def generate_event_brief(db: Session, event_id: int, *, force: bool = False) -> tuple[EventBrief, dict, bool]:
    snapshot, _ = create_event_snapshot(db, event_id, force=False)
    previous = get_previous_event_snapshot(db, event_id, before_snapshot_id=snapshot.id)
    change = compare_event_snapshots(previous, snapshot)

    existing = _existing_event_brief_for_snapshot(db, snapshot.id)
    if existing and not force:
        return existing, change, True

    generation_method = "deterministic"
    model_name = None
    if settings.answer_provider.lower() == "openai":
        try:
            sections = _openai_event_brief_sections(snapshot, previous, change)
            generation_method = "llm_assisted"
            model_name = settings.openai_chat_model
        except Exception:
            sections = _deterministic_brief_sections(snapshot, previous, change)
            create_audit_log(
                db,
                action="event_brief_deterministic_fallback",
                entity_type="event",
                entity_id=str(event_id),
                details="Used deterministic fallback for event brief generation.",
            )
    else:
        sections = _deterministic_brief_sections(snapshot, previous, change)

    snapshot_document_ids = set(snapshot.document_ids or [])
    evidence_document_ids = [
        document_id for document_id in (snapshot.document_ids or []) if document_id in snapshot_document_ids
    ]
    evidence_items = [
        item for item in (snapshot.evidence_items or []) if item.get("document_id") in snapshot_document_ids
    ]

    brief = EventBrief(
        event_id=event_id,
        snapshot_id=snapshot.id,
        previous_snapshot_id=previous.id if previous else None,
        brief_status="draft",
        headline=sections["headline"][:500],
        what_happened=sections.get("what_happened"),
        what_changed=sections.get("what_changed"),
        why_it_matters=sections.get("why_it_matters"),
        confirmed_points=sections.get("confirmed_points") or [],
        uncertainties=sections.get("uncertainties") or [],
        watch_next=sections.get("watch_next") or [],
        evidence_document_ids=evidence_document_ids,
        evidence_items=evidence_items,
        change_summary=change,
        generation_method=generation_method,
        model_name=model_name,
        prompt_version=PROMPT_VERSION if generation_method == "llm_assisted" else None,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)

    create_audit_log(
        db,
        action="generate_event_brief",
        entity_type="event_brief",
        entity_id=str(brief.id),
        details=f"Generated event brief for event {event_id} using {generation_method}.",
    )
    return brief, change, False


def update_event_brief_review(
    db: Session,
    brief_id: int,
    *,
    brief_status: str,
    reviewer_notes: str | None = None,
    reviewer: str = "demo_reviewer",
) -> EventBrief:
    brief = db.query(EventBrief).filter(EventBrief.id == brief_id).first()
    if not brief:
        raise ValueError("Event brief not found")
    if brief_status not in ALLOWED_EVENT_BRIEF_STATUSES:
        raise ValueError(f"Invalid brief_status. Allowed: {sorted(ALLOWED_EVENT_BRIEF_STATUSES)}")

    previous_status = brief.brief_status
    brief.brief_status = brief_status
    brief.reviewer_notes = reviewer_notes
    db.commit()
    db.refresh(brief)

    create_audit_log(
        db,
        action="update_event_brief_review",
        entity_type="event_brief",
        entity_id=str(brief.id),
        actor=reviewer,
        details=f"Review status changed from {previous_status} to {brief_status}.",
    )
    return brief
