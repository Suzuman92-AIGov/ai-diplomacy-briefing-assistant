import json
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.source import Source
from app.models.document import Document
from app.services.audit import create_audit_log
from app.services.ingestion import ingest_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEED_SOURCES_PATH = PROJECT_ROOT / "data" / "seed_sources.json"


def load_seed_source_file() -> list[dict]:
    if not SEED_SOURCES_PATH.exists():
        raise ValueError(f"Seed source file not found: {SEED_SOURCES_PATH}")

    with SEED_SOURCES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_seed_sources(db: Session) -> dict:
    seed_sources = load_seed_source_file()
    created = 0
    existing = 0

    for item in seed_sources:
        source = db.query(Source).filter(Source.name == item["name"]).first()
        if source:
            existing += 1
            continue

        source = Source(
            name=item["name"],
            base_url=item.get("base_url") or item.get("url"),
            source_type=item.get("source_type", "other"),
            reliability_tier=item.get("reliability_tier", "medium"),
            country_or_institution=item.get("country_or_institution"),
            notes=item.get("notes"),
            is_active=True,
        )
        db.add(source)
        created += 1

    db.commit()

    create_audit_log(
        db,
        action="load_seed_sources",
        entity_type="source",
        entity_id=None,
        details=f"Created {created} seed sources; {existing} already existed.",
    )

    return {
        "status": "ok",
        "created": created,
        "existing": existing,
        "total_seed_sources": len(seed_sources),
    }


def list_seed_sources() -> list[dict]:
    return load_seed_source_file()


def ingest_seed_source(db: Session, *, seed_name: str) -> dict:
    seed_sources = load_seed_source_file()
    item = next((x for x in seed_sources if x["name"] == seed_name), None)
    if not item:
        raise ValueError(f"Seed source not found: {seed_name}")

    source = db.query(Source).filter(Source.name == item["name"]).first()
    if not source:
        source = Source(
            name=item["name"],
            base_url=item.get("base_url") or item.get("url"),
            source_type=item.get("source_type", "other"),
            reliability_tier=item.get("reliability_tier", "medium"),
            country_or_institution=item.get("country_or_institution"),
            notes=item.get("notes"),
            is_active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    existing_doc = db.query(Document).filter(Document.url == item["url"]).first()
    if existing_doc:
        return {
            "status": "exists",
            "document_id": existing_doc.id,
            "title": existing_doc.title,
            "url": existing_doc.url,
        }

    document = ingest_url(
        db,
        url=item["url"],
        source_id=source.id,
        topic_tags=item.get("topic_tags"),
        sensitivity_level=item.get("sensitivity_level", "medium"),
        language=None,
    )

    return {
        "status": "ingested",
        "document_id": document.id,
        "title": document.title,
        "url": document.url,
    }



def ingest_seed_sources_batch(db: Session, *, seed_names: list[str]) -> dict:
    results = []

    for seed_name in seed_names:
        try:
            result = ingest_seed_source(db, seed_name=seed_name)
            results.append({
                "seed_name": seed_name,
                "status": result.get("status"),
                "document_id": result.get("document_id"),
                "title": result.get("title"),
                "url": result.get("url"),
                "error": None,
            })
        except Exception as exc:
            results.append({
                "seed_name": seed_name,
                "status": "failed",
                "document_id": None,
                "title": None,
                "url": None,
                "error": str(exc),
            })

    created_or_existing = sum(1 for r in results if r["status"] in {"ingested", "exists"})
    failed = sum(1 for r in results if r["status"] == "failed")

    create_audit_log(
        db,
        action="batch_ingest_seed_sources",
        entity_type="document",
        entity_id=None,
        details=f"Batch seed ingestion completed. Successful/existing: {created_or_existing}; failed: {failed}.",
    )

    return {
        "status": "ok",
        "successful_or_existing": created_or_existing,
        "failed": failed,
        "results": results,
    }



def list_recommended_seed_sources() -> list[dict]:
    seed_sources = load_seed_source_file()
    return [item for item in seed_sources if item.get("demo_recommended") is True]
