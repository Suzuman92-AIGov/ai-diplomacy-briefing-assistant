# v0.10.0 Release Notes

## Release Overview

v0.10.0 is a public documentation release for the current local prototype. It presents AI Diplomacy Briefing Assistant as an evidence-first event-intelligence application for policy and media monitoring.

The release does not claim production readiness. It documents the implemented repository capabilities: source and document evidence, event clustering, evidence timelines, snapshots, deterministic change detection, event briefs, text-based PDF ingestion, search/RAG, document-level briefs, review workflows, exports, and audit logs.

## Event-Intelligence Architecture

The application now supports an event-oriented layer on top of document ingestion:

```text
Source -> Document -> Event -> Event Snapshot -> Change Detection -> Event Brief -> Review
```

Documents remain the evidence layer. Events are deterministic groupings of related documents. Snapshots capture an immutable event state. Change detection compares snapshots before any optional LLM-assisted wording is used.

## Events UI

The Streamlit application includes an Events page with:

- event list and filtering;
- event detail;
- source and publisher coverage;
- related document counts;
- event metadata;
- evidence timeline;
- manual reclustering action;
- explicit snapshot and event-brief controls.

No snapshot or event brief is generated automatically during ordinary page reruns.

## Evidence Timeline

Event detail displays related documents and orders evidence by publication date where available, falling back to fetched date. The UI exposes titles, URLs, source/publisher names, clustering method, relationship type, and similarity score.

## Snapshots

Event snapshots are immutable records containing event metadata, document IDs, source and publisher names, evidence item metadata, latest evidence timestamp, and a deterministic snapshot hash.

If the latest snapshot hash is unchanged, snapshot creation reuses the existing snapshot unless forced.

## Deterministic Change Detection

Change detection compares the current event snapshot with the previous snapshot and reports:

- whether changes exist;
- change level: `none`, `minor`, `meaningful`, or `major`;
- new or removed document IDs;
- new or removed sources and publishers;
- count deltas;
- metadata changes;
- latest evidence date changes;
- deterministic readable summary.

This deterministic comparison is separate from any LLM interpretation.

## Event Briefs

Event briefs are generated from the current event snapshot and the deterministic change result. The persisted brief includes:

- headline;
- what happened;
- what changed;
- why it matters;
- confirmed points;
- uncertainties;
- watch-next items;
- evidence document IDs;
- evidence items;
- generation method;
- review status and reviewer notes.

Brief evidence is limited to documents in the snapshot used for generation.

## Deterministic Fallback

Local mode works without a model-provider key. Event briefs use deterministic wording unless `ANSWER_PROVIDER=openai` is configured successfully. If LLM-assisted event brief generation fails, the service falls back to deterministic sections and records an audit log.

Document-level RAG and document-level brief workflows also support local deterministic behavior.

## Review Workflow

The repository includes review endpoints for document-level briefs and event briefs. Generated outputs remain draft material until reviewed. The review workflow is a local prototype control, not a substitute for production authentication, authorization, or governance policy.

## Text-Based PDF Ingestion

Phase 10A adds reliable text-based PDF ingestion:

- binary-safe download path;
- PDF detection by content type, magic bytes, and URL suffix fallback;
- `pypdf` extraction;
- PDF metadata and title fallback handling;
- NUL/control-character sanitation;
- concise public errors for OCR-not-supported, malformed, encrypted, oversized, timeout, and unsupported-content cases;
- no raw PDF bytes stored in PostgreSQL text fields;
- successful PDFs enter the same document and event-assignment flow as HTML pages.

Image-only or scanned PDFs are not OCRed.

## Japanese and Unicode Handling

Sanitation preserves Japanese and normal Unicode text while removing NUL bytes and invalid control characters. Tests cover Japanese PDF text extraction behavior and multilingual-safe title/content normalization for event matching.

## Initialization and Upgrade Notes

Fresh local databases can be initialized through:

```bash
curl -X POST http://localhost:8002/admin/init-db
```

Existing databases created before the event tables should apply the additive SQL migrations manually:

```bash
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_0900_phase_9a_events.sql
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_1200_phase_9c_event_snapshots_briefs.sql
```

Optional backfill:

```bash
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=true"
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=false"
```

This release does not add or modify database migrations.

## Test Status

The repository contains pytest coverage for:

- source creation and reuse;
- brief review;
- event clustering and backfill;
- event snapshots, change detection, event briefs, and event-brief review;
- frontend event helper parsing/filtering behavior;
- URL ingestion and PDF ingestion edge cases.

Run:

```bash
pytest
python3 -m compileall backend/app frontend tests
git diff --check
```

Record the exact local test result in the completion report for the release preparation task.

## Manual Verification Checklist

- Start PostgreSQL with Docker Compose.
- Start FastAPI on port `8002`.
- Start Streamlit on port `8501`.
- Initialize the database.
- Load or create sources.
- Ingest an HTML page.
- Ingest a small text-based PDF.
- Confirm scanned/image-only PDF returns OCR-not-supported wording.
- Confirm a malformed PDF fails without partial records.
- Open Documents and inspect extracted text.
- Create chunks for search/RAG workflows.
- Open Events and inspect event evidence.
- Create an event snapshot.
- Generate an event brief.
- Review the event brief.
- Run event backfill for older documents if needed.
- Confirm search, RAG, document-level brief generation, review, export, dashboard, and audit logs still work.

## Known Limitations

- No OCR or scanned-PDF text recognition.
- No PDF table/layout reconstruction.
- No scheduled monitoring or alerts.
- No authentication, authorization, or multi-tenant access control.
- No source-independence verification.
- No manual event merge/delete workflow.
- No source refresh/versioning workflow for changed pages.
- Local TF-IDF retrieval is deterministic but limited.
- OpenAI outputs are not automatically approved.
- Document-level brief citations are not immutable evidence snapshots.
- No production deployment hardening or formal security certification.
- FastAPI application metadata still reports an older internal API version because this release is documentation-only.
