# Current Architecture

This document summarizes the repository as prepared for the v0.10.0 public documentation release. For the shorter public overview, see the root [README](../README.md).

## Purpose

AI Diplomacy Briefing Assistant is a local-first event-intelligence prototype for evidence-based policy and media monitoring. It ingests public HTML pages and text-based PDFs, stores documents as evidence, chunks content for retrieval, groups related documents into events, captures event snapshots, detects changes, generates reviewable event briefs, and preserves audit logs.

## Runtime Components

### Backend

The backend is a FastAPI application in `backend/app/main.py`.

Registered route groups:

- health;
- admin/database initialization, seed sources, demo setup, event backfill;
- dashboard metrics;
- sources;
- URL ingestion;
- documents, chunk status, chunking, embedding preparation;
- events, event documents, reclustering;
- event snapshots, event changes, event briefs;
- event-brief review;
- search;
- RAG answers;
- document-level brief generation;
- document-level brief detail and review;
- Markdown export;
- audit logs.

Configuration lives in `backend/app/core/config.py`. Defaults are local-demo oriented with deterministic local retrieval and answer generation. OpenAI-backed retrieval/briefing can be enabled through environment variables.

### Frontend

The frontend is a single Streamlit application in `frontend/streamlit_app.py`. It calls the backend over HTTP using `API_BASE_URL`, defaulting to `http://localhost:8002`.

Current pages include:

- Start Here
- Dashboard
- Events
- System Status
- Sources
- Source Pack
- Ingest URL
- Documents
- Semantic Search
- Ask Knowledge Base
- Generate Brief
- Review Briefs
- Export Brief
- Briefs
- Audit Logs
- Governance

### Database

The database is PostgreSQL with pgvector through `docker-compose.yml`. Fresh local databases are initialized by `POST /admin/init-db`, which calls SQLAlchemy `Base.metadata.create_all`.

Additive SQL migration files exist for event intelligence:

- `backend/migrations/versions/20260702_0900_phase_9a_events.sql`
- `backend/migrations/versions/20260702_1200_phase_9c_event_snapshots_briefs.sql`

These are applied manually for existing databases. The repository does not include Alembic.

## Data Model

### Source

`backend/app/models/source.py`

Approved or manually created source registry entry with name, base URL, source type, reliability tier, institution/country notes, and active status.

### Document

`backend/app/models/document.py`

One ingested HTML page or text-based PDF. Stores title, URL, optional source, extracted text, cleaned text, publication/fetched metadata, language, topic tags, sensitivity level, and status.

### Chunk

`backend/app/models/chunk.py`

Searchable segment of a document. Local mode uses TF-IDF over chunk text. OpenAI mode can store 1536-dimensional embeddings for pgvector search.

### Event and EventDocument

`backend/app/models/event.py`

An event groups related documents around a real-world development. `EventDocument` links documents to events and records relationship type, clustering method, and similarity score.

### EventSnapshot and EventBrief

`backend/app/models/event_intelligence.py`

Snapshots capture immutable event state and evidence metadata. Event briefs are generated from snapshots and deterministic change results, then stored with review status, evidence IDs, evidence items, generation method, and reviewer notes.

### Brief and BriefSource

`backend/app/models/brief.py`

Document-level policy brief and citation links to document/chunk rows. This older workflow remains available alongside event briefs.

### AuditLog

`backend/app/models/audit_log.py`

Records major local workflow actions such as source loading, ingestion, chunking, brief generation, review updates, export, snapshot creation, and event brief generation.

## Ingestion Flow

1. Streamlit or API clients call `POST /ingest/url` or seed-source admin routes.
2. The backend checks for exact duplicate `Document.url`.
3. The URL is downloaded with size and timeout limits.
4. Content type, magic bytes, and URL suffix determine HTML or PDF path.
5. HTML pages are extracted with `trafilatura`, with BeautifulSoup fallback.
6. Text-based PDFs are parsed with `pypdf`.
7. NUL bytes and invalid control characters are removed from persisted text fields.
8. Text length and PDF readability are validated.
9. A `Document` is inserted.
10. The document is assigned to an event.
11. Audit logs record successful ingestion.

Image-only/scanned PDFs fail with OCR-not-supported wording. Malformed, encrypted, oversized, timeout, and unsupported-content cases fail before normal persistence where covered by ingestion validation.

## Event Grouping

Event assignment uses deterministic checks before approximate matching:

- exact canonical URL;
- normalized URL with tracking parameters removed;
- normalized content hash;
- normalized title similarity;
- TF-IDF/character-ngram text similarity over title/summary metadata.

Relevant thresholds:

- `EVENT_NEAR_DUPLICATE_TITLE_THRESHOLD`
- `EVENT_SEMANTIC_SIMILARITY_THRESHOLD`
- `EVENT_TITLE_MATCH_WINDOW_DAYS`

Low-confidence matches create a new event instead of silently joining an uncertain event.

## Retrieval, RAG, and Document Briefs

Local mode:

- builds a `TfidfVectorizer` over all chunks plus the query at request time;
- uses cosine similarity;
- returns top-K chunks.

OpenAI mode:

- embeds the query;
- searches chunk embeddings with pgvector distance.

RAG answers and document-level briefs use retrieved chunks as source context. Document-level brief citation links point to document/chunk IDs and are not immutable evidence snapshots.

## Event Snapshots and Change Detection

Event snapshots store event metadata, document IDs, source/publisher names, evidence items, latest evidence timestamp, and a deterministic snapshot hash.

Change detection compares snapshots and reports:

- no/minor/meaningful/major change level;
- new/removed documents;
- new/removed sources and publishers;
- count deltas;
- metadata changes;
- latest evidence date changes;
- deterministic summary.

This happens before any optional LLM-assisted wording.

## Event Briefing

Event brief generation explicitly creates or reuses a snapshot, compares it with the previous snapshot, and generates a draft event brief from snapshot evidence.

If `ANSWER_PROVIDER=openai` is configured, the service attempts LLM-assisted wording from supplied JSON data only. If that fails, deterministic fallback is used and logged.

Event briefs are not automatically approved.

## Local Deployment Shape

Local development uses:

1. PostgreSQL/pgvector via Docker Compose.
2. FastAPI with Uvicorn on port `8002`.
3. Streamlit on port `8501`.

There is no production web server config, authentication, authorization, managed secret storage, scheduled job runner, deployment manifest, observability stack, or CI workflow in this repository.

## Current Limitations

- No OCR.
- No scheduled monitoring or alerts.
- No manual event merge/delete workflow.
- No authentication or multi-tenant access control.
- No formal migration framework.
- No SSRF hardening for arbitrary URL ingestion.
- No source-independence verification.
- No production deployment hardening.
- FastAPI metadata version in application code still reports an older internal API version.
