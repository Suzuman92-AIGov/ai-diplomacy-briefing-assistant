from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import AuditLog, Document, Event, EventBrief, EventDocument, EventSnapshot, Source
from app.services.event_intelligence import (
    compare_event_snapshots,
    create_event_snapshot,
    generate_event_brief,
    update_event_brief_review,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "backend"
    / "migrations"
    / "versions"
    / "20260702_1200_phase_9c_event_snapshots_briefs.sql"
)


@pytest.fixture()
def intelligence_db(tmp_path):
    database_path = tmp_path / "event_intelligence.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Source.__table__.create(bind=engine)
    Document.__table__.create(bind=engine)
    Event.__table__.create(bind=engine)
    EventDocument.__table__.create(bind=engine)
    EventSnapshot.__table__.create(bind=engine)
    EventBrief.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session, TestingSessionLocal
    finally:
        session.close()
        engine.dispose()


def create_source(session, name="Example Source"):
    source = Source(
        name=name,
        base_url=f"https://{name.lower().replace(' ', '-')}.example.org",
        source_type="official",
        reliability_tier="high",
        country_or_institution="US",
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def create_document(session, source, **overrides):
    values = {
        "source_id": source.id,
        "title": "NIST updates AI governance guidance",
        "url": f"https://example.org/document-{session.query(Document).count() + 1}",
        "published_date": date(2026, 7, 1),
        "language": "English",
        "raw_text": "Raw text about a public AI governance development.",
        "cleaned_text": "Clean text about a public AI governance development with enough detail for evidence.",
        "summary": "Evidence summary about the development.",
        "topic_tags": "AI governance",
        "sensitivity_level": "medium",
        "status": "ingested",
    }
    values.update(overrides)
    document = Document(**values)
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def create_event_with_document(session, source=None):
    source = source or create_source(session)
    document = create_document(session, source)
    event = Event(
        title=document.title,
        normalized_title="nist updates ai governance guidance",
        summary="Initial event summary.",
        event_type="development",
        status="active",
        primary_language="English",
        country_or_region="US",
        first_seen_at=datetime(2026, 7, 1),
        last_seen_at=datetime(2026, 7, 1),
    )
    session.add(event)
    session.flush()
    session.add(
        EventDocument(
            event_id=event.id,
            document_id=document.id,
            relationship_type="primary",
            similarity_score=1.0,
            clustering_method="new_event",
        )
    )
    session.commit()
    session.refresh(event)
    return event, document, source


def add_document_to_event(session, event, source, **overrides):
    document = create_document(session, source, **overrides)
    session.add(
        EventDocument(
            event_id=event.id,
            document_id=document.id,
            relationship_type="primary",
            similarity_score=0.93,
            clustering_method="semantic_title_summary",
        )
    )
    session.commit()
    return document


def test_first_snapshot_creation_and_unchanged_reuse(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)

    first, reused_first = create_event_snapshot(session, event.id)
    second, reused_second = create_event_snapshot(session, event.id)

    assert reused_first is False
    assert first.snapshot_type == "baseline"
    assert first.document_count == 1
    assert reused_second is True
    assert second.id == first.id
    assert session.query(EventSnapshot).count() == 1


def test_forced_snapshot_creation_with_unchanged_hash(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    forced, reused = create_event_snapshot(session, event.id, force=True)

    assert reused is False
    assert forced.id != first.id
    assert forced.snapshot_hash == first.snapshot_hash
    assert forced.snapshot_type == "forced"


def test_new_document_and_new_source_change_snapshot_hash(intelligence_db):
    session, _ = intelligence_db
    event, _, source = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    add_document_to_event(session, event, source, url="https://example.org/new-existing-source")
    second, _ = create_event_snapshot(session, event.id)
    new_source = create_source(session, "Second Publisher")
    add_document_to_event(session, event, new_source, url="https://second.example.org/article")
    third, _ = create_event_snapshot(session, event.id)

    assert second.snapshot_hash != first.snapshot_hash
    assert third.snapshot_hash != second.snapshot_hash
    assert third.distinct_publisher_count == 2


def test_event_metadata_change_changes_hash_and_snapshot_is_immutable(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    event.status = "monitoring"
    event.summary = "Expanded event summary."
    session.commit()
    second, _ = create_event_snapshot(session, event.id)

    assert second.snapshot_hash != first.snapshot_hash
    assert first.event_summary == "Initial event summary."
    assert second.event_summary == "Expanded event summary."


def test_missing_event_snapshot_creation_raises(intelligence_db):
    session, _ = intelligence_db

    with pytest.raises(ValueError, match="Event not found"):
        create_event_snapshot(session, 999)


def test_change_detection_levels_and_removed_relationship(intelligence_db):
    session, _ = intelligence_db
    event, _, source = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    same = compare_event_snapshots(first, first)
    assert same["change_level"] == "none"

    add_document_to_event(session, event, source, url="https://example.org/minor")
    second, _ = create_event_snapshot(session, event.id)
    minor = compare_event_snapshots(first, second)
    assert minor["change_level"] == "minor"
    assert minor["document_count_delta"] == 1

    new_source = create_source(session, "New Publisher")
    add_document_to_event(session, event, new_source, url="https://new.example.org/meaningful")
    third, _ = create_event_snapshot(session, event.id)
    meaningful = compare_event_snapshots(second, third)
    assert meaningful["change_level"] == "meaningful"
    assert meaningful["new_publishers"] == ["New Publisher"]

    link = session.query(EventDocument).filter(EventDocument.document_id == third.document_ids[-1]).first()
    session.delete(link)
    session.commit()
    fourth, _ = create_event_snapshot(session, event.id)
    removed = compare_event_snapshots(third, fourth)
    assert removed["removed_document_ids"]


def test_major_change_detection_with_metadata_and_several_sources(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    for idx in range(3):
        source = create_source(session, f"Major Publisher {idx}")
        add_document_to_event(
            session,
            event,
            source,
            url=f"https://major-{idx}.example.org/article",
            title=f"Major publisher {idx} reports development",
        )
    event.summary = "Substantially expanded summary."
    session.commit()
    second, _ = create_event_snapshot(session, event.id)

    change = compare_event_snapshots(first, second)

    assert change["change_level"] == "major"
    assert change["summary_changed"] is True


def test_first_snapshot_change_result_is_initial_baseline(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)
    snapshot, _ = create_event_snapshot(session, event.id)

    change = compare_event_snapshots(None, snapshot)

    assert change["is_initial_baseline"] is True
    assert change["has_changes"] is False
    assert change["change_level"] == "none"
    assert change["new_document_ids"] == []
    assert change["new_sources"] == []
    assert change["new_publishers"] == []
    assert change["document_count_delta"] == 0
    assert change["source_count_delta"] == 0
    assert change["publisher_count_delta"] == 0
    assert "Initial event baseline" in change["deterministic_change_summary"]


def test_initial_baseline_then_unchanged_then_new_evidence_change_levels(intelligence_db):
    session, _ = intelligence_db
    event, _, source = create_event_with_document(session)
    first, _ = create_event_snapshot(session, event.id)

    baseline = compare_event_snapshots(None, first)
    reused, reused_existing = create_event_snapshot(session, event.id)
    unchanged = compare_event_snapshots(first, reused)
    add_document_to_event(session, event, source, url="https://example.org/genuine-new-evidence")
    second, _ = create_event_snapshot(session, event.id)
    changed = compare_event_snapshots(first, second)

    assert baseline["is_initial_baseline"] is True
    assert baseline["has_changes"] is False
    assert baseline["change_level"] == "none"
    assert reused_existing is True
    assert unchanged["is_initial_baseline"] is False
    assert unchanged["has_changes"] is False
    assert unchanged["change_level"] == "none"
    assert changed["is_initial_baseline"] is False
    assert changed["has_changes"] is True
    assert changed["change_level"] == "minor"
    assert changed["new_document_ids"]


def test_deterministic_brief_generation_idempotency_and_force(intelligence_db):
    session, _ = intelligence_db
    event, document, _ = create_event_with_document(session)

    first, change, reused_first = generate_event_brief(session, event.id)
    second, _, reused_second = generate_event_brief(session, event.id)
    forced, _, reused_forced = generate_event_brief(session, event.id, force=True)

    assert reused_first is False
    assert first.generation_method == "deterministic"
    assert document.id in first.evidence_document_ids
    assert set(first.evidence_document_ids).issubset(set(first.snapshot.document_ids))
    assert "Initial event baseline" in first.what_changed
    assert change["is_initial_baseline"] is True
    assert change["has_changes"] is False
    assert change["change_level"] == "none"
    assert "New evidence document IDs" not in " ".join(first.confirmed_points)
    assert reused_second is True
    assert second.id == first.id
    assert reused_forced is False
    assert forced.id != first.id


def test_llm_assisted_brief_with_mocked_provider(intelligence_db, monkeypatch):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)

    monkeypatch.setattr(settings, "answer_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    def fake_sections(snapshot, previous, change):
        return {
            "headline": "Mocked event brief",
            "what_happened": "Grounded mocked summary.",
            "what_changed": "Grounded mocked change.",
            "why_it_matters": "Grounded mocked interpretation.",
            "confirmed_points": ["Confirmed from snapshot evidence."],
            "uncertainties": ["Requires human review."],
            "watch_next": ["Watch for new evidence."],
        }

    monkeypatch.setattr("app.services.event_intelligence._openai_event_brief_sections", fake_sections)

    brief, _, _ = generate_event_brief(session, event.id, force=True)

    assert brief.generation_method == "llm_assisted"
    assert brief.headline == "Mocked event brief"


def test_malformed_llm_response_uses_deterministic_fallback(intelligence_db, monkeypatch):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)

    monkeypatch.setattr(settings, "answer_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    def fail_sections(snapshot, previous, change):
        raise ValueError("malformed model response")

    monkeypatch.setattr("app.services.event_intelligence._openai_event_brief_sections", fail_sections)

    brief, _, _ = generate_event_brief(session, event.id, force=True)

    assert brief.generation_method == "deterministic"
    assert session.query(AuditLog).filter(AuditLog.action == "event_brief_deterministic_fallback").count() == 1


def test_event_brief_review_workflow(intelligence_db):
    session, _ = intelligence_db
    event, _, _ = create_event_with_document(session)
    brief, _, _ = generate_event_brief(session, event.id)

    updated = update_event_brief_review(
        session,
        brief.id,
        brief_status="reviewed",
        reviewer_notes="Checked evidence.",
        reviewer="reviewer",
    )

    assert updated.brief_status == "reviewed"
    assert updated.reviewer_notes == "Checked evidence."
    assert session.query(AuditLog).filter(AuditLog.action == "update_event_brief_review").count() == 1


def test_event_intelligence_api_routes(intelligence_db):
    session, TestingSessionLocal = intelligence_db
    event, _, _ = create_event_with_document(session)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        missing_latest = client.get(f"/events/{event.id}/snapshots/latest")
        create_response = client.post(f"/events/{event.id}/snapshots")
        latest_response = client.get(f"/events/{event.id}/snapshots/latest")
        list_response = client.get(f"/events/{event.id}/snapshots")
        change_response = client.get(f"/events/{event.id}/changes")
        brief_response = client.post(f"/events/{event.id}/briefs/generate")
        repeat_brief_response = client.post(f"/events/{event.id}/briefs/generate")
        force_brief_response = client.post(f"/events/{event.id}/briefs/generate?force=true")
        briefs_response = client.get(f"/events/{event.id}/briefs")
        brief_id = brief_response.json()["brief"]["id"]
        detail_response = client.get(f"/event-briefs/{brief_id}")
        review_response = client.patch(
            f"/event-briefs/{brief_id}/review",
            json={"brief_status": "approved", "reviewer_notes": "Approved for internal use."},
        )
        missing_event_response = client.post("/events/999/snapshots")
        missing_brief_response = client.get("/event-briefs/999")
    finally:
        app.dependency_overrides.clear()

    assert missing_latest.status_code == 404
    assert create_response.status_code == 200
    assert create_response.json()["snapshot"]["snapshot_type"] == "baseline"
    assert latest_response.status_code == 200
    assert list_response.status_code == 200
    assert change_response.status_code == 200
    assert brief_response.status_code == 200
    assert repeat_brief_response.json()["reused"] is True
    assert force_brief_response.json()["reused"] is False
    assert briefs_response.status_code == 200
    assert detail_response.status_code == 200
    assert review_response.json()["brief_status"] == "approved"
    assert missing_event_response.status_code == 404
    assert missing_brief_response.status_code == 404


def test_event_intelligence_migration_contains_tables_indexes_and_no_title_uniqueness():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS event_snapshots" in sql
    assert "CREATE TABLE IF NOT EXISTS event_briefs" in sql
    assert "ix_event_snapshots_event_id" in sql
    assert "ix_event_snapshots_created_at" in sql
    assert "ix_event_snapshots_snapshot_hash" in sql
    assert "ix_event_briefs_event_id" in sql
    assert "event_title" in sql
    assert "UNIQUE (event_title)" not in sql
    assert "JSONB" in sql
