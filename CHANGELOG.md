# Changelog

This project uses a concise Keep a Changelog-style format.

## [0.10.0] - 2026-07-02

### Added

- Public documentation release positioning the repository as an event-based policy and media intelligence prototype.
- Event-intelligence documentation covering source evidence, documents, events, snapshots, deterministic changes, and event briefs.
- Release notes for v0.10.0.
- GitHub release draft for v0.10.0.
- Current screenshot checklist for dashboard, Events, event detail, evidence timeline, snapshots/change intelligence, event briefs, PDF ingestion, search, and RAG.
- Safe `.env.example` with local deterministic defaults and optional provider settings.

### Changed

- Rewrote the root README around current product behavior rather than chronological phase history.
- Updated local setup instructions to use FastAPI on port `8002` and Streamlit from the repository root on port `8501`.
- Clarified that local deterministic mode works without a model-provider key.
- Clarified which committed screenshots are current for the older document/RAG workflow and which v0.10.0 screenshots are still missing.

### Fixed

- Removed public README reliance on missing setup or screenshot references.
- Corrected stale setup commands that used the old Streamlit port or frontend-local startup path.
- Added notes around historical documentation that predates later event-intelligence, test, and PDF-ingestion work.

### Known Limitations

- Functional local prototype, not production-ready.
- No OCR, scheduled monitoring, alerts, authentication, source-independence verification, or manual event merge/delete workflow.
- Local retrieval is deterministic TF-IDF rather than full multilingual semantic event resolution.
- FastAPI application metadata still reports an older internal API version because this release does not modify application source.
