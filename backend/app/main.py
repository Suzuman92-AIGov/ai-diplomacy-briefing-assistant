from fastapi import FastAPI
from app.api.routes.admin import router as admin_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.export import router as export_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.briefs import router as briefs_router
from app.api.routes.brief_generator import router as brief_generator_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.rag import router as rag_router
from app.api.routes.search import router as search_router
from app.api.routes.sources import router as sources_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.8.0",
    description="RAG-based AI foreign policy briefing assistant with governance controls.",
)

app.include_router(health_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(export_router)
app.include_router(sources_router)
app.include_router(documents_router)
app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(rag_router)
app.include_router(brief_generator_router)
app.include_router(briefs_router)
app.include_router(audit_logs_router)


@app.get("/")
def root():
    return {
        "message": "AI Diplomacy Briefing Assistant API",
        "docs": "/docs",
        "health": "/health",
    }
