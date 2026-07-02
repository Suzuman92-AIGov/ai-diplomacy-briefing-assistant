# Phase 9A Event Intelligence Foundation

## Current Document Flow

The current system is document-first:

1. Streamlit or seed-source routes submit a URL to `/ingest/url` or admin ingestion routes.
2. `backend/app/services/ingestion.py` checks only exact `Document.url` duplication.
3. The page is downloaded, extracted, cleaned, and stored as one `Document`.
4. Chunking, local/OpenAI retrieval, RAG answers, brief generation, review, export, and audit logs all reference document and chunk records.

This preserves source traceability, but it treats every article as a separate unit even when multiple sources report the same real-world development.

## Proposed Event Flow

Phase 9A keeps every `Document` intact and adds event grouping after document creation:

1. Ingestion creates the `Document` as it does today.
2. Event assignment computes deterministic fingerprints:
   - canonical URL
   - normalized URL
   - content hash
   - normalized title
3. Deterministic duplicate checks run before approximate matching.
4. Existing event candidates are retrieved from `EventDocument` links and event title metadata.
5. A document is linked to one primary event when confidence is high enough.
6. A new event is created when no suitable existing event is found.
7. Re-running clustering is idempotent and updates the existing document-event link rather than adding duplicates.

Existing document, chunk, search, RAG, and brief routes remain backward compatible.

## Database Changes

Add `events`:

- `id`
- `title`
- `normalized_title`
- `summary`
- `event_type`
- `status`
- `primary_language`
- `country_or_region`
- `first_seen_at`
- `last_seen_at`
- `created_at`
- `updated_at`

Add `event_documents`:

- `id`
- `event_id`
- `document_id`
- `relationship_type`
- `similarity_score`
- `clustering_method`
- `created_at`

Indexes:

- `events.normalized_title`
- `events.first_seen_at`
- `events.last_seen_at`
- `event_documents.event_id`
- `event_documents.document_id`

Constraints:

- no global uniqueness on `events.normalized_title`; title reuse is resolved by clustering, not the database
- partial unique `event_documents.document_id` where `relationship_type = 'primary'` for the initial one-primary-event rule
- unique `(event_id, document_id)`
- foreign keys to preserve referential integrity

## Clustering Logic

Reusable helpers live in the event intelligence service layer:

- URL normalization removes fragments, lowercases scheme/host, normalizes path slashes, sorts query parameters, and drops tracking parameters such as `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `fbclid`, `gclid`, `msclkid`, and similar click IDs.
- Title normalization lowercases text, trims whitespace, collapses repeated spaces, removes light punctuation, and keeps Japanese and other multilingual text.
- Content hashing uses SHA-256 over normalized cleaned text.
- Duplicate detection checks:
  1. exact canonical URL match
  2. normalized URL match
  3. exact content hash match
  4. near-duplicate normalized title
  5. semantic title/summary similarity
- Candidate retrieval uses existing event-document links and event normalized titles.
- Assignment records `relationship_type`, `similarity_score`, and `clustering_method`.

Thresholds are configurable in `backend/app/core/config.py`:

- near-duplicate title threshold: `0.92`
- semantic title/summary threshold: `0.78`

Low-confidence matches create a new event instead of silently assigning to an uncertain event.

## API Changes

Add routes using existing FastAPI conventions:

- `GET /events`
- `GET /events/{event_id}`
- `GET /events/{event_id}/documents`
- `POST /events/recluster/{document_id}`
- `POST /admin/events/backfill?dry_run=true`

Event detail responses include metadata, related document count, related titles, source/publisher names, publication dates, clustering method, and similarity score.

## Migration And Rollback Plan

Migration file:

- `backend/migrations/versions/20260702_0900_phase_9a_events.sql`

Apply manually against the configured database until the project adopts Alembic:

```bash
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_0900_phase_9a_events.sql
```

Fresh local databases continue to work through `/admin/init-db` because SQLAlchemy models include the new tables.

Dry-run event backfill:

```bash
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=true"
```

Apply event backfill:

```bash
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=false"
```

Rollback for this additive phase:

```sql
DROP TABLE IF EXISTS event_documents;
DROP TABLE IF EXISTS events;
```

The rollback does not delete or alter source documents, chunks, briefs, or audit logs.

## Test Plan

Add regression tests for:

1. identical canonical URLs
2. URLs differing only by tracking parameters
3. exact duplicate content
4. similar titles describing the same event
5. similar topics describing different events
6. English and Japanese titles
7. repeated clustering of the same document
8. event API responses
9. database migration and relationship constraints
10. existing ingestion behavior remaining functional

Tests use SQLite for fast local service coverage and inspect the SQL migration text for required tables, indexes, and constraints.
