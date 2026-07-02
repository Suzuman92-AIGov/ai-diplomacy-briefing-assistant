import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def db_session(tmp_path):
    from app.models.audit_log import AuditLog
    from app.models.brief import Brief

    database_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{database_path}")

    Brief.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def brief_factory(db_session):
    from app.models.brief import Brief

    def create_brief(**overrides):
        values = {
            "title": "Test Brief",
            "brief_type": "policy_brief",
            "query_or_topic": "AI governance",
            "content": "Draft content",
            "sensitivity_level": "medium",
            "confidence_level": "medium",
            "review_status": "draft",
        }
        values.update(overrides)

        brief = Brief(**values)
        db_session.add(brief)
        db_session.commit()
        db_session.refresh(brief)
        return brief

    return create_brief
