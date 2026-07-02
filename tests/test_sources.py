from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.routes.sources import create_source
from app.db.session import get_db
from app.main import app
from app.models import Source
from app.schemas.source import SourceCreate


def source_payload(**overrides):
    values = {
        "name": "European Commission - AI",
        "base_url": "https://digital-strategy.ec.europa.eu/",
        "source_type": "official",
        "reliability_tier": "high",
        "country_or_institution": "EU",
        "notes": "Official EU digital policy source.",
        "is_active": True,
    }
    values.update(overrides)
    return values


def create_source_test_session(tmp_path):
    database_path = tmp_path / "sources.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Source.__table__.create(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, TestingSessionLocal


def test_create_genuinely_new_source_returns_201(tmp_path):
    engine, TestingSessionLocal = create_source_test_session(tmp_path)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post("/sources", json=source_payload(name="  European Commission - AI  "))
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 201
    assert response.json()["name"] == "European Commission - AI"


def test_create_source_whose_name_already_exists_returns_existing(tmp_path):
    engine, TestingSessionLocal = create_source_test_session(tmp_path)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        first = client.post("/sources", json=source_payload())
        second = client.post("/sources", json=source_payload())

        with TestingSessionLocal() as db:
            source_count = db.query(Source).count()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert source_count == 1


def test_create_source_existing_name_with_whitespace_returns_existing(tmp_path):
    engine, TestingSessionLocal = create_source_test_session(tmp_path)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        first = client.post("/sources", json=source_payload())
        second = client.post("/sources", json=source_payload(name="  European Commission - AI  "))

        with TestingSessionLocal() as db:
            source_count = db.query(Source).count()
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert source_count == 1


def test_create_source_integrity_error_rolls_back_and_returns_existing(tmp_path, monkeypatch):
    engine, TestingSessionLocal = create_source_test_session(tmp_path)
    db = TestingSessionLocal()
    response = Response()
    rollback_called = {"value": False}

    original_commit = db.commit
    original_rollback = db.rollback

    def commit_with_race():
        with TestingSessionLocal() as race_db:
            race_db.add(Source(**source_payload()))
            race_db.commit()
        raise IntegrityError("duplicate source name", {}, Exception("duplicate"))

    def tracked_rollback():
        rollback_called["value"] = True
        return original_rollback()

    monkeypatch.setattr(db, "commit", commit_with_race)
    monkeypatch.setattr(db, "rollback", tracked_rollback)

    try:
        result = create_source(SourceCreate(**source_payload()), response=response, db=db)
    finally:
        monkeypatch.setattr(db, "commit", original_commit)
        monkeypatch.setattr(db, "rollback", original_rollback)
        db.close()
        engine.dispose()

    assert rollback_called["value"] is True
    assert response.status_code == 200
    assert result.name == "European Commission - AI"
