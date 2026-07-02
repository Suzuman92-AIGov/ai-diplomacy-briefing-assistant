# Phase 9B Event Intelligence Streamlit UI

## 1. Current Streamlit Architecture And Navigation

The frontend is a single Streamlit application in `frontend/streamlit_app.py`. It configures the page, defines lightweight HTTP helper functions, and selects page content through one sidebar radio navigation control.

Current pages are:

- Start Here
- Dashboard
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

The frontend talks to the FastAPI backend over HTTP using the `API_BASE_URL` environment variable, defaulting to `http://localhost:8002`.

## 2. Current Document-Oriented User Flow

The current workflow starts from source setup and individual document ingestion:

1. Initialize the backend database.
2. Load or create approved sources.
3. Ingest a URL or curated seed source.
4. Browse documents.
5. Chunk and prepare searchable document content.
6. Search chunks, ask questions, generate briefs, review briefs, export Markdown, and inspect audit logs.

This preserves source traceability, but the primary browsing unit is still a document or chunk rather than a real-world event.

## 3. Proposed Event-Oriented User Flow

Phase 9B makes events the main intelligence browsing layer while keeping documents as evidence:

1. Open Events.
2. Review overview metrics from real event API data.
3. Filter and sort events by title, summary, status, type, region, language, document count, and source coverage.
4. Open an event.
5. Review event-level metadata separately from evidence.
6. Inspect supporting documents, source/publisher coverage, clustering method, and similarity score.
7. Review the source timeline ordered by publication date, falling back to fetched date.
8. Use existing ingestion, search, RAG, briefing, review, export, dashboard, and audit pages as before.

## 4. Navigation Changes

Add a visible `Events` page to the existing sidebar navigation. The page is additive and does not remove or hide existing pages.

Recommended placement is after `Dashboard`, because events become the primary intelligence overview while the dashboard remains operational.

## 5. Component Structure

Phase 9B keeps the single-file Streamlit pattern used by the repository:

- API helpers: reusable functions for event list, detail, documents, and reclustering.
- Formatting helpers: dates, datetimes, counts, missing values, similarity scores, and clustering labels.
- Data helpers: response validation, event filtering, sorting, metrics, publisher/source counting, and timeline ordering.
- Events page: overview, refresh, filters, event list, selected event detail, evidence, timeline, and advanced reclustering.

This avoids a broader frontend refactor in this phase.

## 6. Frontend API Client Changes

Add reusable helpers:

- `get_events()`
- `get_event(event_id)`
- `get_event_documents(event_id)`
- `recluster_document(document_id)`

The helpers use explicit request timeouts, validate response shape, sanitize user-facing errors, and avoid exposing SQL, tracebacks, or large backend response bodies.

## 7. Streamlit Session-State And Caching Strategy

Use short-lived session-state caching rather than fetching all data on every rerun:

- Cache the event list for a short TTL.
- Load event detail and documents only when a user opens an event.
- Store the selected event ID in session state.
- Provide a Refresh event data button that clears cached event data.
- Clear relevant cache entries after successful reclustering.

The page must not call detail endpoints for every event on every rerun.

## 8. API Endpoints Used By Each Component

- Event overview: `GET /events`
- Filters and sorting: client-side over the `GET /events` response
- Event list: `GET /events`
- Event detail metadata: `GET /events/{event_id}`
- Supporting documents: `GET /events/{event_id}/documents`
- Advanced reclustering: `POST /events/recluster/{document_id}`

Streamlit must not query PostgreSQL or SQLAlchemy directly.

## 9. Filter And Sorting Behavior

Filters:

- Text search across title and summary.
- Status.
- Event type.
- Country or region.
- Language.
- Minimum document count.
- Multi-source events only.

Filter options are derived from available event data. Missing metadata is handled safely.

Sorting:

- Newest activity / `last_seen_at`.
- First seen.
- Document count.
- Source or publisher count.
- Title.

Missing dates sort deterministically after valid dates for date-descending views.

## 10. Empty, Loading, And Error States

The Events page must handle:

- Backend unavailable.
- Request timeout.
- No events yet.
- Filtered results with no matches.
- Missing event.
- Event with no documents.
- Malformed API response.
- Partial event metadata.
- Reclustering failure.

Errors should be concise and should suggest recovery where useful, such as confirming that the backend is running, refreshing event data, or running event backfill.

## 11. Language-Consistency Policy

The existing Streamlit UI uses English for labels, page titles, buttons, errors, and workflow text. Phase 9B uses English consistently for all new UI. Document titles and article content remain in their original language. Technical clustering values may appear only in advanced sections.

## 12. Test Plan

Add tests for:

- Event API response parsing.
- Event detail parsing.
- Event document parsing.
- Event filtering and sorting.
- Missing optional metadata.
- Empty event lists and filtered empty results.
- Publisher/source deduplication.
- Timeline ordering and fetched-date fallback.
- Date and similarity formatting.
- Clustering method label mapping and unknown fallback.
- Concise API errors for unavailable backend, timeouts, HTTP errors, and malformed JSON.
- Static Streamlit checks for page navigation and no backend calls during import.
- Existing pages still present.
- No placeholder image references.
- Reclustering helper remains explicit-action only.

## 13. Manual Verification Plan

Where the local environment is available:

1. Start PostgreSQL.
2. Start the backend on port `8002`.
3. Start Streamlit on port `8501`.
4. Open the Events page.
5. Confirm that the current three backfilled events are displayed.
6. Open Event 1.
7. Confirm that its related NIST document appears.
8. Confirm that the source/publisher count is correct.
9. Confirm that `new_event` is displayed as `Created as a new event`.
10. Confirm that similarity `1` is formatted as `100%`.
11. Test text filtering.
12. Test status, type, language, and region filters where data exists.
13. Test sorting.
14. Test an event with missing optional metadata.
15. Test the source timeline.
16. Test backend-unavailable behavior.
17. Test manual reclustering if enabled.
18. Confirm that ingestion, search, RAG, briefing, and review pages still open.
19. Confirm that direct PDF ingestion was not modified.

## 14. Features Explicitly Deferred To Later Phases

- PDF extraction.
- OCR.
- Manual event merging.
- Event deletion.
- Automatic event summarization using an LLM.
- Event-level brief generation.
- What changed since the previous briefing.
- Change detection.
- Event alerts.
- Source-reliability scoring.
- Independent-source verification.
- Cross-event relationship graphs.
- Major database redesign.

## 15. Known PDF-Ingestion Issue

Direct PDF URL ingestion may currently process binary PDF content as text and fail because PostgreSQL text fields reject NUL bytes. Phase 9B does not modify PDF ingestion, add OCR, add a PDF library, or expand the scope beyond the event UI. HTML URL ingestion remains the supported path for this phase.
