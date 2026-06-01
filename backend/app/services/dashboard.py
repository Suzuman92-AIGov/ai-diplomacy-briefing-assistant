from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.brief import Brief
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import Source


def _rows_to_dict(rows):
    return {str(key): int(value) for key, value in rows}


def get_dashboard_metrics(db: Session) -> dict:
    total_sources = db.query(Source).count()
    total_documents = db.query(Document).count()
    total_chunks = db.query(Chunk).count()
    searchable_chunks = db.query(Chunk).filter(Chunk.embedding.isnot(None)).count()
    total_briefs = db.query(Brief).count()
    total_audit_logs = db.query(AuditLog).count()

    sources_by_reliability = _rows_to_dict(
        db.query(Source.reliability_tier, func.count(Source.id))
        .group_by(Source.reliability_tier)
        .all()
    )

    sources_by_type = _rows_to_dict(
        db.query(Source.source_type, func.count(Source.id))
        .group_by(Source.source_type)
        .all()
    )

    documents_by_sensitivity = _rows_to_dict(
        db.query(Document.sensitivity_level, func.count(Document.id))
        .group_by(Document.sensitivity_level)
        .all()
    )

    briefs_by_status = _rows_to_dict(
        db.query(Brief.review_status, func.count(Brief.id))
        .group_by(Brief.review_status)
        .all()
    )

    briefs_by_sensitivity = _rows_to_dict(
        db.query(Brief.sensitivity_level, func.count(Brief.id))
        .group_by(Brief.sensitivity_level)
        .all()
    )

    recent_audit_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    recent = [
        {
            "id": log.id,
            "actor": log.actor,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in recent_audit_logs
    ]

    return {
        "totals": {
            "sources": total_sources,
            "documents": total_documents,
            "chunks": total_chunks,
            "searchable_chunks": searchable_chunks,
            "briefs": total_briefs,
            "audit_logs": total_audit_logs,
        },
        "sources_by_reliability": sources_by_reliability,
        "sources_by_type": sources_by_type,
        "documents_by_sensitivity": documents_by_sensitivity,
        "briefs_by_status": briefs_by_status,
        "briefs_by_sensitivity": briefs_by_sensitivity,
        "recent_audit_logs": recent,
    }
