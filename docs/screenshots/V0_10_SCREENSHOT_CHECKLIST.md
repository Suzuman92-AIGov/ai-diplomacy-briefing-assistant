# v0.10.0 Screenshot Checklist

## Current Screenshot Audit

Committed screenshots exist for the older document/RAG workflow:

| File | Status | Notes |
|---|---|---|
| `docs/screenshots/01_start_here-1.png` | Accurate for older Start Here flow | Does not show Events navigation or v0.10 event intelligence. |
| `docs/screenshots/01_start_here-2.png` | Accurate for older Start Here flow | Does not show Events navigation or v0.10 event intelligence. |
| `docs/screenshots/02_dashboard.png` | Outdated for v0.10 navigation | Shows Dashboard, but sidebar predates the Events page. |
| `docs/screenshots/03_source_pack.png` | Accurate for source-pack concept | Does not demonstrate event intelligence. |
| `docs/screenshots/04_documents.png` | Accurate for older document workflow | Does not demonstrate PDF ingestion result or event assignment. |
| `docs/screenshots/05_ask_knowledge_base.png` | Accurate for RAG workflow | Not an event-intelligence screenshot. |
| `docs/screenshots/06_generate_brief.png` | Accurate for document-level brief workflow | Not an event-brief screenshot. |
| `docs/screenshots/07_review_briefs.png` | Accurate for document-level review workflow | Not an event-brief review screenshot. |
| `docs/screenshots/09_audit_logs.png` | Accurate for audit-log concept | Should be refreshed after event/PDF actions for v0.10. |
| `docs/screenshots/10_governance_controls.png` | Accurate for governance concept | Not event-specific. |

Missing v0.10.0 screenshots:

- Events overview.
- Event detail.
- Evidence timeline.
- Event Intelligence snapshot/change section.
- Event brief.
- PDF ingestion success.
- Search or RAG with current navigation.

Do not add fake images, placeholders, local absolute paths, secrets, private documents, API keys, credentials, or unredacted personal data.

## Capture Targets

### 1. Dashboard

- **Page to open**: `Dashboard`
- **Required data/state**: database initialized; a few sources/documents/events available.
- **Suggested filename**: `v0_10_dashboard.png`
- **Demonstrates**: operational totals, source governance, brief governance, audit activity.
- **Exclude/redact**: private source names, internal reviewer names, local filesystem paths.

### 2. Events Overview

- **Page to open**: `Events`
- **Required data/state**: at least two events; one multi-document or multi-source event preferred.
- **Suggested filename**: `v0_10_events_overview.png`
- **Demonstrates**: event list, filters, event metrics, source/publisher coverage.
- **Exclude/redact**: private URLs, credentials, unreleased internal source names.

### 3. Event Detail

- **Page to open**: `Events`, then open one event.
- **Required data/state**: selected event with at least one related document.
- **Suggested filename**: `v0_10_event_detail.png`
- **Demonstrates**: event metadata, related document count, distinct publisher count.
- **Exclude/redact**: sensitive document titles or unpublished URLs.

### 4. Evidence Timeline

- **Page to open**: `Events`, selected event detail.
- **Required data/state**: event with documents that have publication or fetched dates.
- **Suggested filename**: `v0_10_evidence_timeline.png`
- **Demonstrates**: source chronology, evidence titles, source/publisher names, clustering method.
- **Exclude/redact**: private URLs, credentials, sensitive excerpts.

### 5. Event Intelligence Snapshot and Change Section

- **Page to open**: `Events`, selected event detail.
- **Required data/state**: at least one snapshot; preferably two snapshots with a deterministic change.
- **Suggested filename**: `v0_10_event_intelligence_change.png`
- **Demonstrates**: latest snapshot, change level, new documents/sources/publishers, deterministic change summary.
- **Exclude/redact**: internal analyst notes or private records.

### 6. Event Brief

- **Page to open**: `Events`, selected event detail after generating an event brief.
- **Required data/state**: event brief generated from a snapshot.
- **Suggested filename**: `v0_10_event_brief.png`
- **Demonstrates**: headline, what happened, what changed, why it matters, confirmed points, uncertainties, evidence.
- **Exclude/redact**: provider output containing unsupported or sensitive claims; any non-public material.

### 7. PDF Ingestion Success

- **Page to open**: `Ingest URL` or `Documents` after ingestion.
- **Required data/state**: a small public text-based PDF successfully ingested.
- **Suggested filename**: `v0_10_pdf_ingestion_success.png`
- **Demonstrates**: PDF stored as a document with readable extracted text and no NUL-byte error.
- **Exclude/redact**: private PDFs, local file paths, credentials.

### 8. Search or RAG

- **Page to open**: `Semantic Search` or `Ask Knowledge Base`.
- **Required data/state**: chunks created for at least one document.
- **Suggested filename**: `v0_10_search_or_rag.png`
- **Demonstrates**: source-grounded retrieval with citations/excerpts.
- **Exclude/redact**: private questions, sensitive source excerpts, API keys.

## Manual Verification Before Linking Screenshots

- Confirm each image file exists under `docs/screenshots/`.
- Confirm each image is non-empty and visually readable.
- Confirm the UI shown matches current navigation and terminology.
- Confirm no secrets, local absolute paths, private emails, database credentials, tokens, or personal records are visible.
- Add relative links only after the file is committed.
