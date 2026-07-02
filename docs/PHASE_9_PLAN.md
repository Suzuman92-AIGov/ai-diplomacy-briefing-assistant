# Phase 9 Plan

> Historical planning note: this document records the Phase 9 plan as written before later implementation work. Some issues listed here, such as missing tests and the missing frontend PATCH helper, have since been addressed. For current public behavior, see the root [README](../README.md) and [v0.10.0 release notes](RELEASE_NOTES_V0.10.0.md).

This plan turns the audit findings into scoped improvement work. It does not implement the recommendations.

## A. Critical Fixes

### A1. Fix the broken brief review workflow

Relevant files:

- `frontend/streamlit_app.py:22-30`
- `frontend/streamlit_app.py:497-506`
- `backend/app/api/routes/briefs.py:77-114`

Why needed:

The frontend calls `api_patch` when saving a review decision, but no PATCH helper exists. Review is an advertised governance workflow, so this is a functional blocker.

Recommended change:

Add a shared PATCH API helper, reuse common error handling, and add a smoke test that exercises the review page helper path.

### A2. Add database migrations

Relevant files:

- `backend/app/db/init_db.py:11-15`
- `scripts/init_db.sql`
- `backend/app/models/*.py`

Why needed:

The app uses `Base.metadata.create_all`, which cannot safely evolve existing databases. Phase 9 changes will require schema additions for citation snapshots, ingestion metadata, and evaluation data.

Recommended change:

Add Alembic, create a baseline migration for current tables, and replace production schema changes with migration scripts.

### A3. Add authentication and route protection

Relevant files:

- `backend/app/api/routes/admin.py`
- `backend/app/api/routes/ingest.py`
- `backend/app/api/routes/documents.py`
- `backend/app/api/routes/briefs.py`
- `backend/app/api/routes/export.py`
- `backend/app/core/config.py`
- `frontend/streamlit_app.py`

Why needed:

Admin, ingestion, review, export, and audit capabilities are unauthenticated. This is acceptable only for a local demo and blocks production readiness.

Recommended change:

Add an authentication dependency, role checks for admin/reviewer/export actions, and frontend token/session handling appropriate to the deployment target.

### A4. Add SSRF-safe URL ingestion

Relevant files:

- `backend/app/api/routes/ingest.py`
- `backend/app/services/ingestion.py:36-77`
- `backend/app/services/seed_sources.py:98-105`

Why needed:

The backend fetches user-provided URLs. Pydantic `HttpUrl` does not prevent requests to private networks, localhost through redirects, or metadata service addresses.

Recommended change:

Validate scheme, DNS/IP ranges, redirects, content type, response size, and source approval before fetching. Return structured rejection reasons.

### A5. Pin dependencies and add CI

Relevant files:

- `backend/requirements.txt`
- `frontend/requirements.txt`
- repository root CI config to be added

Why needed:

Unpinned dependencies make demos and deployments non-reproducible. No CI currently catches missing functions, migration drift, or broken service behavior.

Recommended change:

Pin or compile dependency versions, add vulnerability scanning, and add CI for tests, linting, import/smoke checks, and migration checks.

## B. Media Intelligence Features

### B1. Add source monitoring and refresh snapshots

Relevant files:

- `backend/app/models/source.py`
- `backend/app/models/document.py`
- `backend/app/services/ingestion.py`
- `backend/app/services/seed_sources.py`
- `data/seed_sources.json`

Why needed:

Media briefing depends on detecting changes over time. Current ingestion rejects duplicate URLs and cannot track updated content.

Recommended change:

Add fetch snapshots or document versions with `content_hash`, `first_seen_at`, `last_seen_at`, `last_checked_at`, `fetch_status`, `http_status`, and changed-content detection.

### B2. Add ingestion jobs and status tracking

Relevant files:

- `backend/app/api/routes/admin.py`
- `backend/app/api/routes/ingest.py`
- `backend/app/services/ingestion.py`
- `backend/app/services/embeddings.py`
- `frontend/streamlit_app.py`

Why needed:

Batch source ingestion and embedding generation are synchronous and can time out. Media monitoring needs reliable background processing and user-visible progress.

Recommended change:

Introduce a job model and queue-backed or lightweight background worker process. Expose job status, per-source failures, retry counts, and logs in the UI.

### B3. Persist richer source governance metadata

Relevant files:

- `data/seed_sources.json`
- `backend/app/models/source.py`
- `backend/app/services/seed_sources.py:23-61`
- `backend/app/schemas/source.py`

Why needed:

Seed source fields such as tags, sensitivity, demo notes, and recommended status are useful for media intelligence but are dropped when loading source rows.

Recommended change:

Add structured tags, region/jurisdiction, outlet/institution type, collection cadence, editorial notes, owner, and approval status to the source model.

### B4. Add article recency and publication intelligence

Relevant files:

- `backend/app/services/ingestion.py:41-67`
- `backend/app/models/document.py`
- `backend/app/services/search.py`
- `frontend/streamlit_app.py`

Why needed:

Briefings need recency, freshness, and date filtering. The current model stores `published_date` when extraction finds it, but retrieval and UI do not use date filters.

Recommended change:

Normalize publication dates, show fetched vs published dates, add date filters to search and brief generation, and flag stale sources.

### B5. Add multilingual media workflow

Relevant files:

- `backend/app/models/document.py:18`
- `backend/app/schemas/ingest.py:9`
- `backend/app/services/ingestion.py`
- `backend/app/services/chunking.py`
- `backend/app/services/search.py:61-66`
- `frontend/streamlit_app.py:279`

Why needed:

The curated source pack includes Japanese and international sources, but local retrieval uses English stop words and language is manually entered or missing.

Recommended change:

Detect language at ingestion, store normalized language codes, use multilingual retrieval settings, add language filters, and optionally store translated summaries.

## C. UX Improvements

### C1. Simplify the workflow navigation

Relevant files:

- `frontend/streamlit_app.py:13-20`

Why needed:

The sidebar exposes many implementation-oriented pages. Non-technical briefing users need workflow-oriented tasks.

Recommended change:

Group pages into Setup, Sources, Ingest, Prepare, Analyze, Briefs, Review/Export, and Audit. Hide lower-level pages behind advanced sections.

### C2. Add bulk document preparation

Relevant files:

- `frontend/streamlit_app.py:288-337`
- `backend/app/api/routes/documents.py`
- `backend/app/services/chunking.py`
- `backend/app/services/embeddings.py`

Why needed:

Users currently select one document at a time to chunk and embed. This is too slow for briefing workflows with multiple sources.

Recommended change:

Add "Prepare all unprepared documents" and status badges. In local mode, clarify that TF-IDF search does not depend on stored placeholder embeddings.

### C3. Improve source and evidence displays

Relevant files:

- `frontend/streamlit_app.py:343-435`
- `frontend/streamlit_app.py:474-482`
- `backend/app/schemas/search.py`
- `backend/app/schemas/rag.py`

Why needed:

Users need to judge source quality quickly. Current source panels show title, URL, IDs, and raw excerpt, but not enough retrieval context.

Recommended change:

Display reliability, source type, date, language, retrieval score, citation label, and why the source was selected. Add warning states for low score or missing source registry linkage.

### C4. Add safer error and status messaging

Relevant files:

- `frontend/streamlit_app.py`
- `backend/app/api/routes/*.py`

Why needed:

The UI often displays raw exception text. This is confusing for users and can expose implementation details.

Recommended change:

Return structured API errors and map them to user-facing messages, with details available only in a debug panel.

### C5. Split the frontend into maintainable modules

Relevant files:

- `frontend/streamlit_app.py`

Why needed:

The single file duplicates API calls, display components, exception handling, and workflow state. This slows future UX work.

Recommended change:

Create a frontend package with `api_client.py`, page modules, shared source/citation components, and shared status/error components.

## D. Evaluation and Testing

### D1. Add service unit tests

Relevant files:

- `backend/app/services/chunking.py`
- `backend/app/services/ingestion.py`
- `backend/app/services/search.py`
- `backend/app/services/rag.py`
- `backend/app/services/brief_generator.py`
- `backend/app/services/export.py`

Why needed:

There are no tests. Core behavior can regress silently.

Recommended change:

Add pytest tests for chunking, duplicate ingestion, extraction errors, local search ranking, RAG citation construction, brief persistence, and export output.

### D2. Add API integration tests

Relevant files:

- `backend/app/main.py`
- `backend/app/api/routes/*.py`
- `backend/app/db/session.py`

Why needed:

Routes handle validation, persistence, and error translation. These contracts need coverage before schema and auth changes.

Recommended change:

Use FastAPI TestClient with a disposable test database or dependency-overridden session. Test admin init, sources, ingestion failures, document chunking, search, brief generation, review, and export.

### D3. Add retrieval and briefing evaluation sets

Relevant files:

- new `evals/` fixtures
- `backend/app/services/search.py`
- `backend/app/services/rag.py`
- `backend/app/services/brief_generator.py`

Why needed:

RAG quality cannot be improved confidently without expected query/source/citation examples.

Recommended change:

Create a small benchmark with representative policy/media questions, expected relevant documents/chunks, expected citations, and unacceptable unsupported claims. Track recall@K, MRR, citation precision, and groundedness.

### D4. Add frontend smoke checks

Relevant files:

- `frontend/streamlit_app.py`

Why needed:

The missing `api_patch` defect would be caught by a simple smoke check.

Recommended change:

Add import/static checks for helper references and, if practical, Streamlit page smoke tests around critical workflows.

### D5. Add model-output validation

Relevant files:

- `backend/app/services/rag.py`
- `backend/app/services/brief_generator.py`
- `backend/app/models/brief.py`

Why needed:

OpenAI mode asks for citations but does not verify them. Local brief mode can include generic policy statements that are not tightly linked to evidence.

Recommended change:

Add citation ID validation, source coverage checks, unsupported-claim heuristics, and a review flag when citation coverage is weak.

## E. Production Readiness

### E1. Add deployment configuration

Relevant files:

- `docker-compose.yml`
- backend Dockerfile to be added
- frontend Dockerfile to be added
- `backend/app/core/config.py`

Why needed:

The current setup is manual and local-only. Production needs separate services, environment-specific config, and secret management.

Recommended change:

Containerize backend and frontend, add production compose or deployment manifests, configure environment-specific settings, and document startup.

### E2. Add observability

Relevant files:

- `backend/app/services/audit.py`
- `backend/app/api/routes/*.py`
- `backend/app/core/config.py`

Why needed:

Audit logs record business events, but production also needs operational logs, request IDs, error traces, timings, and job metrics.

Recommended change:

Add structured logging, request IDs, latency metrics, ingestion/job metrics, and error reporting. Keep audit logs for governance events.

### E3. Harden exports and file handling

Relevant files:

- `backend/app/services/export.py:115-120`
- `backend/app/api/routes/export.py`

Why needed:

The API writes files to local disk and returns full paths. This is fine for local demos but not ideal for production.

Recommended change:

Use configured storage, avoid exposing host paths, add retention rules, and return downloadable content or object identifiers.

### E4. Add immutable citation snapshots

Relevant files:

- `backend/app/models/brief.py:34-42`
- `backend/app/services/brief_generator.py:226-236`
- `backend/app/api/routes/briefs.py:35-57`
- `backend/app/services/export.py:28-99`

Why needed:

Brief traceability currently depends on live chunk rows. Production briefing needs the exact evidence used at generation time.

Recommended change:

Store excerpt, source title, URL, source name, reliability, retrieval score, chunk hash, document hash, and generated-at metadata on each brief citation.

### E5. Add governance-grade roles and review policy

Relevant files:

- `backend/app/api/routes/briefs.py:15-21`
- `backend/app/schemas/review.py`
- `backend/app/models/brief.py`
- `frontend/streamlit_app.py:484-506`

Why needed:

Review status exists, but roles, transitions, required notes, senior-review triggers, and approval rules are not enforced.

Recommended change:

Add role-aware review transitions, require notes for rejection or senior review, block approval of high-sensitivity briefs without senior role, and store authenticated reviewer identity.
