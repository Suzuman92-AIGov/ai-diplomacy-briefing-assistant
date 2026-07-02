import pytest
from fastapi import HTTPException

from app.api.routes.briefs import update_brief_review
from app.models.audit_log import AuditLog
from app.models.brief import Brief
from app.schemas.review import BriefReviewUpdate


def test_allowed_review_status_updates_brief(db_session, brief_factory):
    brief = brief_factory()
    payload = BriefReviewUpdate(
        review_status="reviewed",
        reviewer_notes="Checked source trail.",
        reviewer="analyst_1",
    )

    response = update_brief_review(brief.id, payload, db_session)

    updated = db_session.get(Brief, brief.id)
    assert response.review_status == "reviewed"
    assert response.reviewer_notes == "Checked source trail."
    assert updated.review_status == "reviewed"
    assert updated.reviewer_notes == "Checked source trail."


def test_invalid_review_status_returns_400(db_session, brief_factory):
    brief = brief_factory()
    payload = BriefReviewUpdate(review_status="published")

    with pytest.raises(HTTPException) as exc_info:
        update_brief_review(brief.id, payload, db_session)

    assert exc_info.value.status_code == 400
    assert "Invalid review_status" in exc_info.value.detail


def test_brief_not_found_returns_404(db_session):
    payload = BriefReviewUpdate(review_status="reviewed")

    with pytest.raises(HTTPException) as exc_info:
        update_brief_review(999, payload, db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Brief not found"


def test_review_notes_and_reviewer_are_persisted_where_supported(db_session, brief_factory):
    brief = brief_factory()
    payload = BriefReviewUpdate(
        review_status="needs_senior_review",
        reviewer_notes="Sensitive geopolitical framing needs escalation.",
        reviewer="senior_reviewer",
    )

    update_brief_review(brief.id, payload, db_session)

    updated = db_session.get(Brief, brief.id)
    audit_log = db_session.query(AuditLog).filter(AuditLog.entity_id == str(brief.id)).one()

    assert updated.reviewer_notes == "Sensitive geopolitical framing needs escalation."
    assert audit_log.actor == "senior_reviewer"
    assert audit_log.action == "update_brief_review"
    assert "draft to needs_senior_review" in audit_log.details
