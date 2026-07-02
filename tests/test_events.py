from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import app
from app.models import Document, Event, EventDocument, Source
from app.services.events import (
    assign_document_to_event,
    document_seen_at,
    find_duplicate_document,
    normalize_title,
    normalize_url,
    semantic_text_similarity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = PROJECT_ROOT / "backend" / "migrations" / "versions" / "20260702_0900_phase_9a_events.sql"


@pytest.fixture()
def event_db(tmp_path):
    database_path = tmp_path / "events.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Source.__table__.create(bind=engine)
    Document.__table__.create(bind=engine)
    Event.__table__.create(bind=engine)
    EventDocument.__table__.create(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session, TestingSessionLocal
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def source(event_db):
    session, _ = event_db
    item = Source(
        name="Example Source",
        base_url="https://example.org",
        source_type="official",
        reliability_tier="high",
        country_or_institution="EU",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def create_document(session, source, **overrides):
    values = {
        "source_id": source.id,
        "title": "EU AI Act enforcement timeline announced",
        "url": f"https://example.org/article-{session.query(Document).count() + 1}",
        "published_date": date(2026, 1, 1),
        "language": "English",
        "raw_text": "Raw evidence text about a specific AI governance development.",
        "cleaned_text": "Clean evidence text about a specific AI governance development.",
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


def test_identical_canonical_urls_are_detected_before_event_assignment(event_db, source):
    session, _ = event_db
    existing = create_document(session, source, url="https://example.org/policy")
    candidate = Document(
        title="Candidate",
        url="https://example.org/policy",
        cleaned_text="Different text.",
    )

    duplicate, method, score = find_duplicate_document(session, candidate)

    assert duplicate.id == existing.id
    assert method == "exact_canonical_url"
    assert score == 1.0


def test_urls_differing_only_by_tracking_parameters_share_event(event_db, source):
    session, _ = event_db
    first = create_document(session, source, url="https://example.org/policy?ref=brief&utm_source=newsletter")
    second = create_document(
        session,
        source,
        url="https://example.org/policy?utm_campaign=launch&ref=brief&fbclid=abc123",
        title="Different outlet reports EU AI Act enforcement timeline",
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    assert normalize_url(first.url) == normalize_url(second.url)
    assert second_link.event_id == first_link.event_id
    assert second_link.clustering_method == "normalized_url"


def test_exact_duplicate_content_shares_event(event_db, source):
    session, _ = event_db
    content = "The commission announced a specific implementation timeline for AI Act enforcement."
    first = create_document(session, source, title="EU AI Act timeline", cleaned_text=content)
    second = create_document(
        session,
        source,
        title="Commission implementation schedule",
        url="https://example.org/duplicate-content",
        cleaned_text=content,
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    assert second_link.event_id == first_link.event_id
    assert second_link.clustering_method == "content_hash"


def test_similar_titles_describing_same_event_share_event(event_db, source):
    session, _ = event_db
    first = create_document(session, source, title="EU AI Act enforcement timeline announced")
    second = create_document(
        session,
        source,
        title="EU AI Act enforcement timeline announcement",
        url="https://example.org/similar-title",
        cleaned_text="A second source reports the same enforcement timeline.",
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    assert second_link.event_id == first_link.event_id
    assert second_link.clustering_method == "near_duplicate_title"


def test_similar_topics_describing_different_events_create_separate_events(event_db, source):
    session, _ = event_db
    first = create_document(
        session,
        source,
        title="EU announces AI Act enforcement timeline",
        cleaned_text="The EU announced a timeline for AI Act enforcement.",
    )
    second = create_document(
        session,
        source,
        title="Japan announces AI safety funding plan",
        url="https://example.org/japan-ai-funding",
        cleaned_text="Japan announced funding for AI safety research.",
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    assert second_link.event_id != first_link.event_id
    assert second_link.clustering_method == "new_event"


def test_two_separate_events_can_share_same_normalized_title(event_db, source):
    session, _ = event_db
    first = create_document(
        session,
        source,
        title="Government publishes annual AI report",
        published_date=date(2026, 1, 1),
        cleaned_text="The 2026 annual AI report was published.",
    )
    second = create_document(
        session,
        source,
        title="Government publishes annual AI report",
        url="https://example.org/annual-ai-report-2027",
        published_date=date(2027, 1, 1),
        cleaned_text="The 2027 annual AI report was published.",
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    first_event = session.get(Event, first_link.event_id)
    second_event = session.get(Event, second_link.event_id)
    assert first_event.normalized_title == second_event.normalized_title
    assert first_event.id != second_event.id


def test_recurring_events_with_identical_titles_on_different_dates_create_new_events(event_db, source):
    session, _ = event_db
    first = create_document(
        session,
        source,
        title="Cabinet approves AI policy package",
        published_date=date(2026, 2, 1),
        cleaned_text="The cabinet approved an AI policy package in February.",
    )
    second = create_document(
        session,
        source,
        title="Cabinet approves AI policy package",
        url="https://example.org/ai-policy-package-may",
        published_date=date(2026, 5, 1),
        cleaned_text="The cabinet approved another AI policy package in May.",
    )

    first_link = assign_document_to_event(session, document_id=first.id)
    second_link = assign_document_to_event(session, document_id=second.id)

    assert second_link.event_id != first_link.event_id
    assert second_link.clustering_method == "new_event"


def test_low_confidence_older_event_with_same_normalized_title_creates_new_event(event_db, source):
    session, _ = event_db
    old_document = create_document(
        session,
        source,
        title="Regulator opens AI consultation",
        published_date=date(2025, 1, 15),
        cleaned_text="A regulator opened an AI consultation in 2025.",
    )
    new_document = create_document(
        session,
        source,
        title="Regulator opens AI consultation",
        url="https://example.org/regulator-ai-consultation-2026",
        published_date=date(2026, 7, 1),
        cleaned_text="A regulator opened a separate AI consultation in 2026.",
    )

    old_link = assign_document_to_event(session, document_id=old_document.id)
    new_link = assign_document_to_event(session, document_id=new_document.id)

    assert new_link.event_id != old_link.event_id
    assert new_link.clustering_method == "new_event"


def test_english_and_japanese_titles_can_cluster_deterministically(event_db, source):
    session, _ = event_db
    english = create_document(
        session,
        source,
        title="Japan government announces AI Safety Institute",
        language="English",
        cleaned_text="One English source reports the institute announcement.",
    )
    english_variant = create_document(
        session,
        source,
        title="Japanese government announces AI Safety Institute",
        url="https://example.org/japan-ai-safety-institute",
        language="English",
        cleaned_text="Another English source reports the same institute announcement.",
    )
    japanese = create_document(
        session,
        source,
        title="日本政府、AI安全性研究所を発表",
        url="https://example.org/japanese-ai-safety-1",
        language="Japanese",
        cleaned_text="日本語の本文 一つ目",
    )
    japanese_variant = create_document(
        session,
        source,
        title="日本政府がAI安全性研究所を発表",
        url="https://example.org/japanese-ai-safety-2",
        language="Japanese",
        cleaned_text="日本語の本文 二つ目",
    )

    english_link = assign_document_to_event(session, document_id=english.id)
    english_variant_link = assign_document_to_event(session, document_id=english_variant.id)
    japanese_link = assign_document_to_event(session, document_id=japanese.id)
    japanese_variant_link = assign_document_to_event(session, document_id=japanese_variant.id)

    assert normalize_title(japanese.title)
    assert english_variant_link.event_id == english_link.event_id
    assert japanese_variant_link.event_id == japanese_link.event_id


def test_japanese_semantic_similarity_uses_character_ngrams_without_whitespace():
    same_development_score = semantic_text_similarity(
        "日本政府AI安全性研究所発表",
        "日本政府AI安全性研究所発表詳報",
    )
    different_development_score = semantic_text_similarity(
        "日本政府AI安全性研究所発表",
        "米国政府AI規制方針発表",
    )

    assert same_development_score >= 0.78
    assert different_development_score < 0.78


def test_repeated_clustering_of_same_document_is_idempotent(event_db, source):
    session, _ = event_db
    document = create_document(session, source)

    first_link = assign_document_to_event(session, document_id=document.id)
    second_link = assign_document_to_event(session, document_id=document.id)

    assert second_link.id == first_link.id
    assert session.query(EventDocument).filter_by(document_id=document.id).count() == 1


def test_event_api_responses(event_db, source):
    session, TestingSessionLocal = event_db
    document = create_document(session, source)
    link = assign_document_to_event(session, document_id=document.id)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        list_response = client.get("/events")
        detail_response = client.get(f"/events/{link.event_id}")
        documents_response = client.get(f"/events/{link.event_id}/documents")
        recluster_response = client.post(f"/events/recluster/{document.id}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()[0]["related_document_count"] == 1
    assert list_response.json()[0]["distinct_source_count"] == 1
    assert list_response.json()[0]["distinct_publisher_count"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["related_documents"][0]["document_title"] == document.title
    assert documents_response.status_code == 200
    assert documents_response.json()[0]["clustering_method"] == "new_event"
    assert recluster_response.status_code == 200
    assert recluster_response.json()["event_id"] == link.event_id


def test_event_backfill_dry_run_and_apply_are_repeatable(event_db, source):
    session, TestingSessionLocal = event_db
    first = create_document(session, source, title="Backfill event one")
    second = create_document(session, source, title="Backfill event two", url="https://example.org/backfill-two")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        dry_run_response = client.post("/admin/events/backfill?dry_run=true")
        dry_run_link_count = session.query(EventDocument).count()
        apply_response = client.post("/admin/events/backfill?dry_run=false")
        repeat_response = client.post("/admin/events/backfill?dry_run=false")
    finally:
        app.dependency_overrides.clear()

    session.expire_all()
    assert dry_run_response.status_code == 200
    assert dry_run_response.json()["dry_run"] is True
    assert len(dry_run_response.json()["proposed_groups"]) == 2
    assert dry_run_link_count == 0
    assert apply_response.status_code == 200
    assert repeat_response.status_code == 200
    assert session.query(EventDocument).count() == 2
    assert {first.id, second.id} == {item.document_id for item in session.query(EventDocument).all()}


def test_event_relationship_uniqueness_constraint(event_db, source):
    session, _ = event_db
    document = create_document(session, source)
    link = assign_document_to_event(session, document_id=document.id)
    duplicate_link = EventDocument(
        event_id=link.event_id,
        document_id=document.id,
        relationship_type="primary",
        similarity_score=1.0,
        clustering_method="duplicate_test",
    )

    session.add(duplicate_link)
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplicate_event_document_relationship_is_rejected(event_db, source):
    session, _ = event_db
    document = create_document(session, source)
    link = assign_document_to_event(session, document_id=document.id)
    duplicate_secondary_link = EventDocument(
        event_id=link.event_id,
        document_id=document.id,
        relationship_type="secondary",
        similarity_score=0.7,
        clustering_method="duplicate_pair_test",
    )

    session.add(duplicate_secondary_link)
    with pytest.raises(IntegrityError):
        session.commit()


def test_document_can_have_one_primary_and_one_secondary_relationship(event_db, source):
    session, _ = event_db
    document = create_document(session, source)
    primary_link = assign_document_to_event(session, document_id=document.id)
    secondary_event = Event(
        title="Related diplomatic reaction",
        normalized_title="related diplomatic reaction",
        event_type="reaction",
        status="active",
        first_seen_at=document_seen_at(document),
        last_seen_at=document_seen_at(document),
    )
    session.add(secondary_event)
    session.flush()
    session.add(
        EventDocument(
            event_id=secondary_event.id,
            document_id=document.id,
            relationship_type="secondary",
            similarity_score=0.62,
            clustering_method="manual_related_event",
        )
    )
    session.commit()

    links = session.query(EventDocument).filter_by(document_id=document.id).all()
    assert {link.relationship_type for link in links} == {"primary", "secondary"}
    assert {link.event_id for link in links} == {primary_link.event_id, secondary_event.id}


def test_two_primary_relationships_for_same_document_are_rejected(event_db, source):
    session, _ = event_db
    document = create_document(session, source)
    assign_document_to_event(session, document_id=document.id)
    second_event = Event(
        title="Conflicting primary event",
        normalized_title="conflicting primary event",
        event_type="development",
        status="active",
        first_seen_at=document_seen_at(document),
        last_seen_at=document_seen_at(document),
    )
    session.add(second_event)
    session.flush()
    session.add(
        EventDocument(
            event_id=second_event.id,
            document_id=document.id,
            relationship_type="primary",
            similarity_score=0.99,
            clustering_method="duplicate_primary_test",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_event_migration_contains_tables_indexes_and_constraints():
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS events" in sql
    assert "CREATE TABLE IF NOT EXISTS event_documents" in sql
    assert "ix_events_normalized_title" in sql
    assert "ix_events_first_seen_at" in sql
    assert "ix_events_last_seen_at" in sql
    assert "ix_event_documents_event_id" in sql
    assert "ix_event_documents_document_id" in sql
    assert "uq_events_normalized_title" not in sql
    assert "uq_event_documents_document_id" not in sql
    assert "uq_event_documents_primary_document" in sql
    assert "WHERE relationship_type = 'primary'" in sql
