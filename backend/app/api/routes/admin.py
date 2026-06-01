from fastapi import APIRouter
from app.db.init_db import init_db
from app.db.session import get_db
from app.services.seed_sources import ingest_seed_source, ingest_seed_sources_batch, list_recommended_seed_sources, list_seed_sources, load_seed_sources
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.seed_sources import BatchSeedIngestRequest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/init-db")
def initialize_database():
    init_db()
    return {
        "status": "ok",
        "message": "Database initialized.",
    }


@router.get("/seed-sources")
def get_seed_sources():
    return list_seed_sources()


@router.post("/load-seed-sources")
def load_seed_sources_endpoint(db: Session = Depends(get_db)):
    return load_seed_sources(db)


@router.post("/ingest-seed-source")
def ingest_seed_source_endpoint(seed_name: str, db: Session = Depends(get_db)):
    try:
        return ingest_seed_source(db, seed_name=seed_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Seed ingestion failed: {exc}") from exc



@router.post("/ingest-seed-sources-batch")
def ingest_seed_sources_batch_endpoint(payload: BatchSeedIngestRequest, db: Session = Depends(get_db)):
    return ingest_seed_sources_batch(db, seed_names=payload.seed_names)



@router.get("/recommended-seed-sources")
def get_recommended_seed_sources():
    return list_recommended_seed_sources()


@router.post("/demo-setup")
def demo_setup_endpoint(db: Session = Depends(get_db)):
    load_result = load_seed_sources(db)
    recommended = list_recommended_seed_sources()
    recommended_names = [item["name"] for item in recommended[:3]]
    ingest_result = ingest_seed_sources_batch(db, seed_names=recommended_names)
    return {
        "status": "ok",
        "message": "Demo setup completed. Curated sources loaded and recommended demo sources ingested.",
        "loaded_sources": load_result,
        "recommended_ingested": ingest_result,
    }
