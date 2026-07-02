# Phase 9C Event Briefing And Change Intelligence

## 1. Existing Event And Briefing Flow

Phase 9A adds event grouping after URL ingestion. Original `Document` rows remain the evidence layer, and each document may be linked to an `Event` through `EventDocument`. Phase 9B adds a Streamlit Events page that lists events, opens event detail, displays evidence rows, shows timelines, and exposes manual reclustering.

The existing briefing workflow is still document/retrieval oriented:

1. A user enters a topic.
2. Search retrieves chunks from documents.
3. `generate_policy_brief` creates a document-grounded policy brief.
4. `Brief` and `BriefSource` persist the draft and citation links.
5. Review routes allow status updates and audit logging.

There is no persisted event state comparison yet. The app can show grouped documents, but it cannot tell what changed since a previous event review.

## 2. Proposed Event-Snapshot Flow

Phase 9C adds immutable event snapshots:

1. A user opens an event.
2. The user explicitly creates a snapshot.
3. The backend builds a canonical event-state payload from current event metadata and event-document links.
4. A deterministic hash is calculated.
5. If the latest snapshot has the same hash, the latest snapshot is reused unless `force=true`.
6. If the event materially changed, a new immutable `EventSnapshot` is stored.
7. Change detection compares the current snapshot to the previous stored snapshot.

Snapshots represent event state at a specific time and include event metadata, document IDs, source/publisher names, evidence dates, evidence item metadata, and generation timestamp.

## 3. Change-Detection Architecture

Change detection is deterministic and runs before any LLM-assisted interpretation.

`compare_event_snapshots(previous_snapshot, current_snapshot)` returns:

- whether changes exist;
- change level: `none`, `minor`, `meaningful`, or `major`;
- new and removed document IDs;
- new and removed sources;
- new and removed publishers;
- document/source/publisher count deltas;
- metadata changes;
- latest evidence date changes;
- summary changes;
- a deterministic readable summary.

Rules:

- unchanged snapshot hash: `none`;
- first snapshot without previous baseline: explicit initial baseline with `has_changes=false`, `change_level=none`, and no new/removed deltas;
- one new document from an existing publisher, with no metadata change: `minor`;
- first document from a new source or publisher: `meaningful`;
- changed status, event type, region, language, or summary: `meaningful`;
- several new sources/publishers plus metadata or summary change: `major`.

The deterministic result stays separate from generated interpretation.

## 4. Event-Brief Architecture

Phase 9C adds event-level briefs through a separate `EventBrief` model. An event brief records:

- the current snapshot used;
- the previous snapshot used for comparison, if any;
- the deterministic change result;
- generated sections;
- evidence document IDs;
- generation method: `deterministic` or `llm_assisted`;
- review status and reviewer notes.

Generating a brief is explicit and uses `POST`, never a GET request or ordinary Streamlit rerun.

## 5. Database Changes

Add `event_snapshots`:

- `id`
- `event_id`
- `snapshot_type`
- `event_title`
- `event_summary`
- `event_status`
- `event_type`
- `country_or_region`
- `primary_language`
- `document_count`
- `distinct_source_count`
- `distinct_publisher_count`
- `document_ids`
- `source_names`
- `publisher_names`
- `evidence_items`
- `latest_evidence_at`
- `snapshot_hash`
- `created_at`

Add `event_briefs`:

- `id`
- `event_id`
- `snapshot_id`
- `previous_snapshot_id`
- `brief_status`
- `reviewer_notes`
- `headline`
- `what_happened`
- `what_changed`
- `why_it_matters`
- `confirmed_points`
- `uncertainties`
- `watch_next`
- `evidence_document_ids`
- `evidence_items`
- `change_summary`
- `generation_method`
- `model_name`
- `prompt_version`
- `created_at`
- `updated_at`

Structured lists use JSON/JSONB. Indexes are added for snapshot `event_id`, `created_at`, and `snapshot_hash`, and for event brief `event_id`, `snapshot_id`, and `created_at`.

## 6. API Changes

Add routes:

- `POST /events/{event_id}/snapshots`
- `GET /events/{event_id}/snapshots`
- `GET /events/{event_id}/snapshots/latest`
- `GET /events/{event_id}/changes`
- `POST /events/{event_id}/briefs/generate`
- `GET /events/{event_id}/briefs`
- `GET /event-briefs/{brief_id}`
- `PATCH /event-briefs/{brief_id}/review`

GET routes are read-only. POST snapshot creation and brief generation are explicit user actions. Brief generation is idempotent for unchanged snapshots unless `force=true`.

## 7. LLM And Deterministic Responsibility Boundaries

Deterministic code is responsible for:

- snapshot construction;
- snapshot hashes;
- document/source/publisher deltas;
- metadata and summary changes;
- change level;
- evidence document ID validation;
- fallback brief generation.

LLM assistance, when configured, may improve wording only. It must use supplied snapshot/change/evidence data and must not invent unsupported facts. If the LLM is unavailable, times out, or returns malformed content, deterministic fallback is used.

## 8. Evidence And Citation Behavior

Every event brief is grounded in the snapshot evidence items. Evidence items include:

- document ID;
- title;
- source or publisher;
- URL;
- publication date;
- fetched date;
- relationship type;
- short excerpt where available.

The brief stores evidence document IDs and evidence metadata. It must not cite document IDs outside the snapshot used to create the brief.

## 9. Confidence And Uncertainty Behavior

The deterministic brief separates confirmed points from uncertainties. Confirmed points are limited to event metadata and linked evidence records. Uncertainties include missing previous snapshots, no meaningful change, missing publication dates, single-source coverage, or insufficient evidence for interpretation.

The system does not claim source independence merely because publishers differ.

## 10. Streamlit Changes

Extend the Events detail view with an Event Intelligence section:

- current event state;
- latest snapshot timestamp;
- change level;
- change summary;
- new document/source/publisher counts;
- latest event brief;
- explicit buttons for `Create snapshot`, `Generate event brief`, and `Refresh intelligence`;
- compact history table for snapshots and briefs.

No snapshot or brief is created during ordinary reruns.

## 11. Backward-Compatibility Plan

Phase 9C is additive:

- no existing event/document tables are destructively changed;
- existing Phase 9A clustering remains intact;
- existing Phase 9B browsing remains intact;
- existing document-level `Brief` workflow remains intact;
- existing ingestion, search, RAG, dashboard, export, review, and audit routes remain available.

## 12. Migration And Rollback Plan

Migration file:

- `backend/migrations/versions/20260702_1200_phase_9c_event_snapshots_briefs.sql`

Apply manually:

```bash
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_1200_phase_9c_event_snapshots_briefs.sql
```

Rollback:

```sql
DROP TABLE IF EXISTS event_briefs;
DROP TABLE IF EXISTS event_snapshots;
```

Rollback does not alter `events`, `event_documents`, `documents`, chunks, or existing briefs.

## 13. Test Plan

Tests cover:

- first snapshot creation;
- unchanged snapshot reuse;
- forced snapshot creation;
- new document/source/metadata hash changes;
- immutable snapshot behavior by not updating previous rows;
- missing event;
- snapshot ordering;
- deterministic no/minor/meaningful/major change levels;
- removed relationship handling;
- deterministic fallback brief;
- mocked LLM-assisted brief;
- malformed/timeout LLM fallback;
- evidence IDs retained and validated against the snapshot;
- unchanged brief idempotency and `force=true`;
- API routes and missing resources;
- no generation from GET;
- event brief review update;
- Streamlit explicit-action controls, history display, cache clearing, and no placeholder/mixed-language regressions.

## 14. Manual Verification Plan

1. Start PostgreSQL.
2. Start the backend.
3. Start Streamlit.
4. Open Event 1.
5. Create the first snapshot.
6. Confirm it is marked as an initial baseline.
7. Generate an event brief.
8. Confirm event evidence is shown.
9. Create a second snapshot without changing the event.
10. Confirm the unchanged snapshot is reused.
11. Add or assign a new test document to the event.
12. Create a new snapshot.
13. Confirm the new document appears in change detection.
14. Confirm document and publisher deltas are correct.
15. Generate a new event brief.
16. Confirm What changed reflects only the new state.
17. Confirm previous briefs remain available.
18. Confirm existing Phase 9B filters and evidence views remain functional.
19. Confirm existing search, RAG, ingestion, and briefing pages still load.
20. Confirm PDF ingestion was not changed.

## 15. Features Deferred To Later Phases

- PDF extraction.
- OCR.
- Autonomous continuous monitoring.
- Scheduled snapshot creation.
- Email or Slack alerts.
- Source-reliability scoring.
- Claims that publishers are independent.
- Manual event merging.
- Event deletion.
- Cross-event graphs.
- Automatic impact scoring.
- User-specific personalized relevance.
- Billing.
- Multi-tenant access control.

## 16. Known PDF-Ingestion Limitation

Direct PDF URL ingestion may currently process binary PDF content as text and fail because PostgreSQL text fields reject NUL bytes. Phase 9C does not modify PDF ingestion, add OCR, add PDF libraries, add binary storage, or add PDF-specific extraction logic.
