# Technical Audit

> Historical note: this audit describes the repository at an earlier stage. Several findings have since changed, including the missing `api_patch` helper, absence of tests, default frontend API port, event-intelligence support, and PDF ingestion support. For the current public overview, see the root [README](../README.md) and [v0.10.0 release notes](RELEASE_NOTES_V0.10.0.md).

This audit is read-only with respect to application code. The only repository changes made for the audit are the requested documentation files.

## Executive Summary

The repository implements a clear local demo of a source-grounded briefing workflow, but it is not yet production-ready. The strongest parts are the simple end-to-end flow, curated seed source pack, local/offline demo mode, and explicit governance concepts. The biggest risks are lack of migrations, weak ingestion reliability, retrieval quality limits, missing tests, no auth, permissive free-form data contracts, and incomplete citation immutability.

Critical defects found at the time of the audit:

- The Streamlit review workflow was broken because `api_patch` was called but not defined in `frontend/streamlit_app.py:497-506`. The current frontend includes `api_patch`.
- There is no migration framework; schema creation depends on `Base.metadata.create_all` in `backend/app/db/init_db.py:11-15`.
- At the time of the audit, there were no tests in the repository. The current repository includes pytest tests under `tests/`.
- Admin, ingestion, export, and review endpoints have no authentication or authorization.
- Citation traceability is reference-based but not immutable because `BriefSource` stores only IDs and a label in `backend/app/models/brief.py:34-42`.

## 1. Current Architecture and Data Flow

The current architecture is a three-part local application:

- FastAPI backend in `backend/app/main.py`
- Streamlit frontend in `frontend/streamlit_app.py`
- PostgreSQL/pgvector database via `docker-compose.yml`

The implemented flow is:

`seed source registry or manual source -> URL ingestion -> document row -> chunk rows -> local TF-IDF or pgvector retrieval -> RAG answer or brief generation -> review -> Markdown export -> audit logs`

Relevant files:

- `backend/app/main.py`: API composition
- `frontend/streamlit_app.py`: single-file UI and HTTP client
- `backend/app/services/seed_sources.py`: seed source loading and batch ingestion
- `backend/app/services/ingestion.py`: URL extraction
- `backend/app/services/chunking.py`: text chunking
- `backend/app/services/embeddings.py`: embedding preparation
- `backend/app/services/search.py`: retrieval
- `backend/app/services/rag.py`: question answering
- `backend/app/services/brief_generator.py`: brief generation
- `backend/app/services/export.py`: Markdown export

Assessment:

- The separation between routes, services, schemas, and models is a good foundation.
- Business logic is concentrated in service modules, which is workable for this repo size.
- The frontend is operationally useful but too large and repetitive as a single Streamlit file.
- The architecture is synchronous and request-bound. Long URL ingestion, embeddings, and batch ingestion run inside HTTP requests.

Recommendations:

- Introduce background jobs for ingestion and embeddings in `backend/app/services/ingestion.py`, `backend/app/services/embeddings.py`, and `backend/app/api/routes/admin.py` because network fetches and model calls can exceed frontend/API timeouts.
- Add a clear job/status model and route set because the frontend currently waits on long synchronous calls in `frontend/streamlit_app.py:27-29`.
- Split `frontend/streamlit_app.py` into page modules and a shared API client because it currently mixes navigation, API transport, data formatting, and workflow state.

## 2. Database Models and Migrations

Current models:

- `Source`: `backend/app/models/source.py`
- `Document`: `backend/app/models/document.py`
- `Chunk`: `backend/app/models/chunk.py`
- `Brief` and `BriefSource`: `backend/app/models/brief.py`
- `AuditLog`: `backend/app/models/audit_log.py`

Schema creation:

- `backend/app/db/init_db.py:11-15` creates pgvector extension and calls `Base.metadata.create_all`.
- `scripts/init_db.sql` only creates the vector extension.
- There is no Alembic folder, migration script, or migration config.

Findings:

- No migration history means schema changes cannot be applied safely to existing databases.
- `Chunk.embedding` is fixed to `Vector(1536)` in `backend/app/models/chunk.py:18`, which tightly couples the database to the configured embedding dimension.
- `Document.url` is unique in `backend/app/models/document.py:14`, which prevents re-ingesting a changed page as a new document version.
- `Source.name` is unique in `backend/app/models/source.py:11`, but seed source updates are skipped if a source already exists in `backend/app/services/seed_sources.py:28-32`.
- `BriefSource` has no excerpt snapshot, retrieval score, source URL/title snapshot, generated-at metadata, or source content checksum.
- Many operational fields are free-form strings: document status, source tier/type, sensitivity, language, confidence, and review status.

Recommendations:

- Add Alembic migrations for all current tables because `create_all` cannot manage production schema evolution.
- Add controlled enums or validated literals in schemas and models for source type, reliability tier, sensitivity, document status, confidence, and review status because invalid strings currently flow through APIs such as `backend/app/schemas/ingest.py:4-9`.
- Add document versioning fields such as `content_hash`, `fetch_status`, `http_status`, `last_checked_at`, and `source_snapshot_id` in `backend/app/models/document.py` because media pages change over time.
- Add chunk versioning fields such as `chunker_version`, `content_hash`, `start_offset`, `end_offset`, and `embedding_model` in `backend/app/models/chunk.py` because retrieval and citation quality depend on reproducible chunks.
- Expand `BriefSource` in `backend/app/models/brief.py` to store generation-time title, URL, excerpt, source name, reliability tier, retrieval score, and content hash because brief citations should remain auditable after source or chunk changes.

## 3. Ingestion Reliability

Current implementation:

- URL fetch and extraction happen in `backend/app/services/ingestion.py:36-77`.
- `trafilatura.fetch_url` downloads the page.
- `trafilatura.extract` extracts text.
- BeautifulSoup full-page text is used as fallback.
- Text shorter than 200 characters is rejected.
- Duplicate URL ingestion raises a `ValueError`.
- Batch seed ingestion catches per-source exceptions in `backend/app/services/seed_sources.py:116-156`.

Findings:

- No retry, backoff, timeout tuning, redirect recording, user-agent control, or HTTP status capture is implemented.
- Failures are returned as strings, not structured error categories.
- Extraction quality is not scored. A page with navigation-heavy fallback text can be accepted if over 200 characters.
- No document content hash exists, so the app cannot detect source changes.
- There is no refresh/re-ingestion path because URL is unique and duplicates are rejected in `backend/app/services/ingestion.py:89-91`.
- No file/document ingestion path is present, despite the app description mentioning document ingestion.
- There is no domain allowlist or SSRF protection around user-submitted URLs beyond Pydantic `HttpUrl`.

Recommendations:

- Add structured ingestion results in `backend/app/services/ingestion.py` with status, error code, HTTP status, final URL, content hash, extraction method, extracted length, and language.
- Use retry/backoff and explicit timeouts for URL fetches because `tenacity` is already in `backend/requirements.txt` but unused.
- Add refresh semantics rather than rejecting existing URLs. Store new document versions or fetch snapshots in `backend/app/models/document.py`.
- Add SSRF protections in `backend/app/api/routes/ingest.py` and `backend/app/services/ingestion.py`: block localhost/private IP ranges, enforce allowed schemes, validate redirects, and optionally require source registry approval.
- Add file upload ingestion routes and parsers if document ingestion remains a product requirement.

## 4. RAG and Retrieval Quality

Current implementation:

- Local mode uses TF-IDF in `backend/app/services/search.py:43-95`.
- OpenAI mode uses query embedding and pgvector L2 distance in `backend/app/services/search.py:10-40`.
- Local placeholder embeddings are stored in `backend/app/services/embeddings.py:25-39` but not used for local retrieval.

Findings:

- Local TF-IDF rebuilds the vectorizer on every search over all chunks. This is simple but does not scale.
- Local TF-IDF uses English stop words, which weakens multilingual retrieval.
- There is no similarity threshold; the top K results are returned even when scores are poor.
- There is no source diversity. Multiple chunks from one document can crowd out other sources.
- There is no metadata filtering by source type, reliability, date, country, topic, language, or sensitivity.
- There is no hybrid retrieval, reranking, query rewriting, or evaluation set.
- OpenAI mode does not record embedding model or dimensions per chunk.

Recommendations:

- Add retrieval filters to `backend/app/api/routes/search.py`, `backend/app/schemas/search.py`, and `backend/app/services/search.py` because media intelligence workflows need time, source, jurisdiction, reliability, and language constraints.
- Add score thresholds and zero-score suppression in local retrieval because irrelevant chunks can currently be returned as evidence.
- Add document/source diversity logic because briefs should not overrepresent one page.
- Add retrieval evaluation fixtures and metrics for recall@K, MRR, citation precision, and unsupported-answer rate.
- Add a hybrid retrieval design: lexical BM25/TF-IDF plus vector search, then rerank.

## 5. Language Handling

Current implementation:

- `Document.language` exists in `backend/app/models/document.py:18`.
- Manual URL ingestion accepts `language` in `backend/app/schemas/ingest.py:9`.
- Streamlit sends a free-form default of `"English"` in `frontend/streamlit_app.py:279`.
- Seed source ingestion sends `language=None` in `backend/app/services/seed_sources.py:98-105`.
- Chunking and TF-IDF are not language-aware.

Findings:

- There is no language detection.
- Language values are not normalized to ISO codes.
- Japanese and other non-English sources are included in `data/seed_sources.json`, but local retrieval uses English stop words in `backend/app/services/search.py:61-66`.
- No translation, cross-lingual embedding strategy, multilingual query handling, or language-specific chunking exists.

Recommendations:

- Normalize language to ISO 639-1 or BCP 47 codes in `backend/app/schemas/ingest.py` and `backend/app/models/document.py`.
- Add language detection during ingestion in `backend/app/services/ingestion.py` because users should not manually label language.
- Use multilingual-aware retrieval and chunking in `backend/app/services/search.py` and `backend/app/services/chunking.py`.
- Add optional translation or bilingual display fields for multilingual media monitoring.

## 6. Briefing Generation and Citation Traceability

Current implementation:

- RAG citations are built in `backend/app/services/rag.py:15-31`.
- Local RAG answers quote excerpts in `backend/app/services/rag.py:34-55`.
- OpenAI RAG prompt asks for bracket citations in `backend/app/services/rag.py:74-88`.
- Brief generation persists `Brief` rows and `BriefSource` joins in `backend/app/services/brief_generator.py:200-255`.
- Brief detail and export reconstruct source evidence from live chunk rows in `backend/app/api/routes/briefs.py:35-57` and `backend/app/services/export.py:28-99`.

Findings:

- Citation labels map to retrieved chunks, but the exact generation-time evidence is not snapshotted.
- OpenAI-generated citations are not validated against available source numbers.
- Local brief generation includes generic policy language in `backend/app/services/brief_generator.py:84-142`, which can go beyond exact retrieved evidence.
- Confidence level is set to `"medium"` whenever results exist in `backend/app/services/brief_generator.py:219`, with no quality calculation.
- Sensitivity classification is keyword-based in `backend/app/services/brief_generator.py:17-33`.

Recommendations:

- Add citation validation after LLM generation in `backend/app/services/rag.py` and `backend/app/services/brief_generator.py` because bracket citations can drift.
- Store immutable citation snapshots in `BriefSource` because exports and review should show generation-time evidence, not live mutable chunk content.
- Separate retrieved evidence, generated synthesis, and analyst notes in the brief model because governance depends on distinguishing source text from AI interpretation.
- Replace the current confidence heuristic with retrieval-quality signals: score threshold, source diversity, official-source count, citation coverage, and recency.

## 7. Frontend UX Problems

Current frontend:

- Single large file: `frontend/streamlit_app.py`
- Sidebar with many pages
- Repeated try/except and API display patterns

Findings:

- Historical finding: the Review Briefs save action was broken because `api_patch` was undefined. The current frontend includes `api_patch`.
- The current `API_BASE_URL` default is `http://localhost:8002`.
- The app exposes too many workflow pages at once for non-technical users.
- Document preparation is manual per document. Users must know to chunk and embed before asking.
- Local mode search does not require embeddings, but UI language says "Generate embeddings" and "Searchable chunks", which can mislead users.
- Error messages often display raw exception text.
- There is no progress/status view for long ingestion or embedding operations.
- Forms use free-form text for language, reviewer, topic tags, and notes with little validation.

Recommendations:

- Add the missing PATCH client in `frontend/streamlit_app.py` because review is a core advertised workflow.
- Align default frontend `API_BASE_URL` with setup docs or make it explicit in the UI.
- Convert the workflow into task-oriented pages: Setup, Sources, Ingest, Prepare, Analyze, Briefs, Review/Export, Audit.
- Add bulk prepare actions for chunking and embedding documents because per-document buttons are slow for media workflows.
- Add source and document health badges to reduce ambiguity around "ingested", "chunked", and "searchable".

## 8. Testing Coverage

Historical state at the time of this audit:

- No test files were found under `backend` or `frontend` at the time. The current repository includes pytest coverage under `tests/`.
- No pytest config, CI workflow, or test database setup exists.
- Python files parse successfully with `ast.parse`, but no behavioral tests were run.

High-priority missing tests:

- `backend/app/services/chunking.py`: chunk boundaries, overlap, idempotency.
- `backend/app/services/ingestion.py`: duplicate URLs, extraction fallback, short extraction failure, source lookup.
- `backend/app/services/search.py`: local retrieval ranking, zero-match behavior, top K limits.
- `backend/app/services/rag.py`: citation construction, empty retrieval behavior.
- `backend/app/services/brief_generator.py`: brief persistence and source joins.
- `backend/app/api/routes/briefs.py`: review status validation.
- `frontend/streamlit_app.py`: smoke test for missing helper functions and page import/runtime errors.

Recommendations:

- Add unit tests around service functions first because most business logic is already in services.
- Add API tests with dependency-overridden test database sessions.
- Add a small deterministic fixture corpus for retrieval evaluation.
- Add CI to run formatting, linting, tests, and migration checks.

## 9. Security and Configuration Risks

Findings:

- No authentication or authorization protects admin, ingestion, review, export, or audit routes.
- `/admin/init-db`, `/admin/demo-setup`, and seed ingestion routes are public within the running API.
- Database defaults use `postgres:postgres` in `backend/app/core/config.py:8` and `docker-compose.yml`.
- User-submitted URLs can trigger backend network requests with no SSRF guard.
- API export writes files to local disk in `backend/app/services/export.py:115-120`.
- CORS is not configured. This is acceptable for local-only use, but undefined for deployment.
- Dependencies in `backend/requirements.txt` and `frontend/requirements.txt` are unpinned.
- Raw exception details are returned in multiple routes, for example `backend/app/api/routes/ingest.py:23-25`, `backend/app/api/routes/search.py:17-19`, and `backend/app/api/routes/brief_generator.py:21-23`.
- Audit actors are user-provided strings, not authenticated identities.

Recommendations:

- Add authentication and role-based authorization before any deployment.
- Protect admin routes separately because they mutate schema and ingest external content.
- Add SSRF protections to ingestion.
- Pin dependencies and introduce dependency vulnerability scanning.
- Replace raw exception responses with structured safe errors and server-side logging.
- Move export storage to a configured safe directory and validate file lifecycle.

## 10. Code Duplication and Technical Debt

Findings:

- `frontend/streamlit_app.py` duplicates API calls, error handling, display patterns, source expanders, and status rendering.
- RAG and brief generation duplicate prompt/source block construction in `backend/app/services/rag.py` and `backend/app/services/brief_generator.py`.
- Brief detail and export duplicate citation-row reconstruction logic in `backend/app/api/routes/briefs.py` and `backend/app/services/export.py`.
- Allowed values are duplicated between frontend selectboxes and backend route checks.
- Audit logging uses free-form strings across services with no event constants.
- There are formatting inconsistencies and compressed one-line try/except blocks in the frontend.

Recommendations:

- Add shared backend citation/evidence serialization utilities because brief detail, export, RAG, and generation need consistent citation structures.
- Add shared prompt/source-block utilities for RAG and brief generation.
- Extract a frontend API client and reusable display helpers.
- Centralize allowed status/type/tier values in backend schemas and expose them to the frontend.
- Add linting and formatting tooling to keep the codebase consistent.

## Overall Readiness

Current readiness: strong local portfolio demo, early prototype for production.

Production blockers:

- migrations
- auth and admin protection
- SSRF-safe ingestion
- test coverage
- background job model
- immutable citation snapshots
- retrieval evaluation
- dependency pinning and environment hardening
