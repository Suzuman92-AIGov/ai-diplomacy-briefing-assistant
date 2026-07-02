# Project Status

## Current Public Positioning

**v0.10.0 documentation release: functional local event-intelligence prototype.**

The repository now presents the application as an evidence-first media and policy intelligence proof of concept rather than a phase-by-phase demo package.

## Working Features

- FastAPI backend and Streamlit frontend.
- PostgreSQL persistence through Docker Compose.
- Curated public-source pack and source registry.
- HTML URL ingestion.
- Text-based PDF ingestion with binary-safe extraction.
- Unicode and Japanese text preservation in ingestion tests.
- NUL/control-character sanitation.
- Document storage and chunking.
- Local TF-IDF retrieval mode.
- Optional OpenAI/pgvector retrieval mode.
- RAG question answering.
- Document-level policy brief generation.
- Document-level brief review and Markdown export.
- Event clustering and event evidence views.
- Event snapshots and deterministic change detection.
- Event brief generation with deterministic fallback.
- Event-brief review workflow.
- Dashboard and audit logs.
- Automated pytest coverage.

## Not Production Ready

Known limitations include no authentication, no scheduled monitoring, no OCR, no alerts, no manual event merge/delete controls, limited local retrieval quality, no production deployment hardening, and no formal security/compliance certification.

See [README.md](README.md), [CHANGELOG.md](CHANGELOG.md), and [docs/RELEASE_NOTES_V0.10.0.md](docs/RELEASE_NOTES_V0.10.0.md) for the current public release description.
