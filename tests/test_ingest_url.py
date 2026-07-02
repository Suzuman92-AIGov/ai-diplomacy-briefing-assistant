import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.ingest import ingest_public_url
from app.api.routes.sources import create_source
from app.models import AuditLog, Document, Source
from app.schemas.ingest import UrlIngestRequest
from app.schemas.source import SourceCreate
from app.services.ingestion import ExtractedArticle


@pytest.fixture()
def ingest_db_session(tmp_path):
    database_path = tmp_path / "ingest.db"
    engine = create_engine(f"sqlite:///{database_path}")

    Source.__table__.create(bind=engine)
    Document.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def extracted_article(monkeypatch):
    def stub_extract_article_from_url(url: str) -> ExtractedArticle:
        return ExtractedArticle(
            title="Stubbed policy article",
            raw_text="Raw evidence text. " * 20,
            cleaned_text="Clean evidence text. " * 20,
        )

    monkeypatch.setattr(
        "app.services.ingestion.extract_article_from_url",
        stub_extract_article_from_url,
    )


def test_ingest_url_without_source_id(ingest_db_session, extracted_article):
    payload = UrlIngestRequest(
        url="https://example.org/no-source",
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    response = ingest_public_url(payload, ingest_db_session)

    document = ingest_db_session.get(Document, response.document_id)
    assert response.status == "ok"
    assert document.source_id is None
    assert document.url == "https://example.org/no-source"


def test_ingest_url_with_valid_source_id(ingest_db_session, extracted_article):
    source = Source(
        name="Example Ministry",
        base_url="https://example.org",
        source_type="government",
        reliability_tier="high",
    )
    ingest_db_session.add(source)
    ingest_db_session.commit()
    ingest_db_session.refresh(source)

    payload = UrlIngestRequest(
        url="https://example.org/valid-source",
        source_id=source.id,
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    response = ingest_public_url(payload, ingest_db_session)

    document = ingest_db_session.get(Document, response.document_id)
    assert response.status == "ok"
    assert document.source_id == source.id


def test_ingest_url_with_invalid_source_id_returns_400(ingest_db_session, monkeypatch):
    def fail_if_article_extraction_runs(url: str) -> ExtractedArticle:
        raise AssertionError("Article extraction should not run for invalid source_id")

    monkeypatch.setattr(
        "app.services.ingestion.extract_article_from_url",
        fail_if_article_extraction_runs,
    )
    payload = UrlIngestRequest(
        url="https://example.org/invalid-source",
        source_id=999,
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    with pytest.raises(HTTPException) as exc_info:
        ingest_public_url(payload, ingest_db_session)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Source with id=999 does not exist."


def test_url_ingestion_with_existing_source(ingest_db_session, extracted_article):
    source = Source(
        name="Existing Source",
        base_url="https://example.org",
        source_type="official",
        reliability_tier="high",
    )
    ingest_db_session.add(source)
    ingest_db_session.commit()
    ingest_db_session.refresh(source)

    response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/existing-source-ingest",
            source_id=source.id,
            topic_tags="diplomacy",
            sensitivity_level="medium",
            language="English",
        ),
        ingest_db_session,
    )

    document = ingest_db_session.get(Document, response.document_id)
    assert document.source_id == source.id


def test_url_ingestion_with_newly_created_source(ingest_db_session, extracted_article):
    source = create_source(
        SourceCreate(
            name="  Newly Created Source  ",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )

    response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/newly-created-source-ingest",
            source_id=source.id,
            topic_tags="diplomacy",
            sensitivity_level="medium",
            language="English",
        ),
        ingest_db_session,
    )

    document = ingest_db_session.get(Document, response.document_id)
    assert source.name == "Newly Created Source"
    assert document.source_id == source.id


def test_url_ingestion_repeated_source_creation_reuses_same_source(
    ingest_db_session,
    extracted_article,
):
    first_source = create_source(
        SourceCreate(
            name="Repeated Source",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )
    second_source = create_source(
        SourceCreate(
            name="  Repeated Source  ",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )

    first_response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/repeated-source-ingest-1",
            source_id=first_source.id,
        ),
        ingest_db_session,
    )
    second_response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/repeated-source-ingest-2",
            source_id=second_source.id,
        ),
        ingest_db_session,
    )

    first_document = ingest_db_session.get(Document, first_response.document_id)
    second_document = ingest_db_session.get(Document, second_response.document_id)
    assert second_source.id == first_source.id
    assert ingest_db_session.query(Source).count() == 1
    assert first_document.source_id == first_source.id
    assert second_document.source_id == first_source.id


def test_url_ingest_request_rejects_placeholder_source_id_zero():
    with pytest.raises(ValidationError):
        UrlIngestRequest(
            url="https://example.org/placeholder-source",
            source_id=0,
        )
