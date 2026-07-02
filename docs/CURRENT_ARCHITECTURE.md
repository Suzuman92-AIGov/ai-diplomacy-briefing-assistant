# Current Architecture

This document describes the repository as implemented at the time of audit. It intentionally separates current behavior from planned or implied behavior in the existing README and portfolio docs.

## System Purpose

The application is a local-first AI diplomacy and media briefing prototype. It ingests public URLs from a curated or manually created source registry, extracts and chunks text, retrieves relevant chunks, answers questions, generates policy briefs, routes briefs through a simple review workflow, exports Markdown, and records audit logs.

## Runtime Components

### Backend

The backend is a FastAPI app in `backend/app/main.py`. It registers routers for:

- health: `backend/app/api/routes/health.py`
- admin and seed sources: `backend/app/api/routes/admin.py`
- dashboard metrics: `backend/app/api/routes/dashboard.py`
- source registry: `backend/app/api/routes/sources.py`
- URL ingestion: `backend/app/api/routes/ingest.py`
- documents, chunking, and embeddings: `backend/app/api/routes/documents.py`
- search: `backend/app/api/routes/search.py`
- RAG answers: `backend/app/api/routes/rag.py`
- brief generation: `backend/app/api/routes/brief_generator.py`
- brief review/detail: `backend/app/api/routes/briefs.py`
- Markdown export: `backend/app/api/routes/export.py`
- audit logs: `backend/app/api/routes/audit_logs.py`

Configuration lives in `backend/app/core/config.py`. Defaults are local demo oriented:

- `database_url`: local PostgreSQL with user/password `postgres:postgres`
- `embedding_provider`: `local`
- `answer_provider`: `local`
- optional OpenAI models for embeddings and chat

### Frontend

The frontend is a single Streamlit file: `frontend/streamlit_app.py`. It calls the backend over HTTP using `requests` and exposes pages for onboarding, dashboard, system status, source management, seed source ingestion, URL ingestion, document operations, search, Q&A, brief generation, review, export, audit logs, and governance notes.

Important current frontend detail: only `api_get` and `api_post` helpers are defined in `frontend/streamlit_app.py:22-30`, but the review workflow calls an undefined `api_patch` at `frontend/streamlit_app.py:497-506`.

### Database

The database is PostgreSQL with pgvector, provided by `docker-compose.yml`. The only SQL initialization file is `scripts/init_db.sql`, which runs `CREATE EXTENSION IF NOT EXISTS vector`.

Application tables are created by SQLAlchemy metadata in `backend/app/db/init_db.py:11-15` through `Base.metadata.create_all`. There is no Alembic or other migration framework in the repository.

## Data Model

### Source

Defined in `backend/app/models/source.py`.

Purpose: approved source registry entry.

Key fields:

- `name`, unique
- `base_url`
- `source_type`
- `reliability_tier`
- `country_or_institution`
- `notes`
- `is_active`

Relationships:

- one source has many documents

Current limitation: source policy metadata in `data/seed_sources.json`, such as `topic_tags`, `sensitivity_level`, `demo_recommended`, and `demo_notes`, is not fully persisted on the `sources` table.

### Document

Defined in `backend/app/models/document.py`.

Purpose: one ingested URL and its extracted text.

Key fields:

- `source_id`
- `title`
- `url`, unique
- `published_date`
- `fetched_at`
- `language`
- `raw_text`
- `cleaned_text`
- `summary`
- `topic_tags`
- `sensitivity_level`
- `status`

Relationships:

- many documents belong to one source
- one document has many chunks
- one document can be linked to many brief citations

Current limitation: `language`, `topic_tags`, `sensitivity_level`, and `status` are free-form strings rather than controlled values.

### Chunk

Defined in `backend/app/models/chunk.py`.

Purpose: searchable segment of a document.

Key fields:

- `document_id`
- `chunk_index`
- `content`
- `token_count`
- `embedding` as `Vector(1536)`

Current limitation: chunks have no version, source text checksum, retrieval metadata, or immutable citation snapshot.

### Brief and BriefSource

Defined in `backend/app/models/brief.py`.

Purpose:

- `Brief` stores generated policy brief content and review status.
- `BriefSource` links a brief to source chunks by `document_id`, `chunk_id`, and `citation_label`.

Current limitation: `BriefSource` stores references only. It does not persist the cited excerpt, URL, title, source metadata, retrieval score, or generation-time evidence snapshot.

### AuditLog

Defined in `backend/app/models/audit_log.py`.

Purpose: records major actions with actor, action, entity, details, and timestamp.

Current limitation: logs are free-form text without structured event payloads, request IDs, source checksums, or authenticated actors.

## Current Data Flow

### Seed Source Loading

1. Streamlit calls `/admin/load-seed-sources`.
2. `backend/app/api/routes/admin.py` delegates to `load_seed_sources`.
3. `backend/app/services/seed_sources.py` reads `data/seed_sources.json`.
4. New `Source` rows are inserted by source name.
5. An audit log is written.

Current behavior:

- Existing sources are skipped by name.
- Seed source fields not present on `Source` are dropped during source loading.
- Source updates are not applied if a seed source already exists.

### URL Ingestion

1. Streamlit calls `/ingest/url` or `/admin/ingest-seed-source`.
2. `backend/app/services/ingestion.py` checks for duplicate `Document.url`.
3. `trafilatura.fetch_url` downloads the page.
4. `trafilatura.extract_metadata` and `trafilatura.extract` extract metadata and text.
5. BeautifulSoup fallback uses full page text if trafilatura extraction fails.
6. Text is normalized by stripping blank lines.
7. A minimum cleaned text length of 200 characters is required.
8. A `Document` row is inserted.
9. An audit log is written.

Current behavior:

- Ingestion is synchronous.
- There is no retry/backoff despite `tenacity` being listed in requirements.
- There is no content hash, fetch status history, HTTP metadata, redirect record, or robots/domain allowlist enforcement.
- Language is accepted from the request but not detected.
- Seed source ingestion passes `language=None`.

### Chunking

1. Streamlit calls `/documents/{document_id}/chunk`.
2. `chunk_document` reads `Document.cleaned_text`.
3. If chunks already exist, it returns the existing count and does not recreate chunks.
4. Otherwise `chunk_text` slices text by character offsets using a default chunk size of 1200 characters and overlap of 200 characters.
5. New `Chunk` rows are inserted with approximate token counts.
6. Document status becomes `chunked`.
7. An audit log is written.

Current behavior:

- Existing chunks are preserved to avoid breaking current brief references.
- Chunking is not sentence-aware, paragraph-aware, token-aware, or language-aware.
- There is no chunk versioning path for improved chunking while preserving old citations.

### Embedding Preparation

1. Streamlit calls `/documents/{document_id}/embed`.
2. `embed_document_chunks` loads all chunks for the document.
3. In local mode, `embed_text_local_placeholder` writes deterministic random 1536-dimensional vectors.
4. In OpenAI mode, `embed_text_openai` calls the configured OpenAI embedding model.
5. Document status becomes `embedded_local` or `embedded`.
6. An audit log is written.

Current behavior:

- Local mode does not use stored vectors for retrieval.
- OpenAI mode assumes a 1536-dimensional embedding model because `Chunk.embedding` is `Vector(1536)`.
- There is no batching, rate-limit handling, retry, partial failure handling, or embedding model/version metadata on chunks.

### Retrieval

Retrieval is implemented in `backend/app/services/search.py`.

Local mode:

1. Loads all chunks and related document/source rows.
2. Builds a fresh `TfidfVectorizer` over all chunk text plus the query on each request.
3. Uses cosine similarity and returns the top K chunks.

OpenAI mode:

1. Embeds the query with `embed_text`.
2. Uses pgvector `l2_distance` against stored chunk embeddings.
3. Returns the top K chunks with distance.

Current behavior:

- There are no filters for source type, reliability tier, date, language, jurisdiction, topic, or sensitivity.
- There is no score threshold.
- Local TF-IDF returns top K even when similarity is zero.
- There is no reranker, query expansion, hybrid retrieval, deduplication by document, or source diversity logic.

### RAG Answering

Implemented in `backend/app/services/rag.py`.

1. `answer_question` calls `semantic_search`.
2. Citations are built from retrieved chunks.
3. Local mode returns extractive bullet excerpts.
4. OpenAI mode prompts a chat model to answer only from supplied chunks and cite bracket numbers.
5. The response returns answer text, providers, and citations.

Current behavior:

- RAG answers are not persisted.
- There is no validation that OpenAI output citations match supplied citation IDs.
- There is no groundedness or citation coverage check.
- Local mode is extractive and safer but low quality as synthesis.

### Brief Generation

Implemented in `backend/app/services/brief_generator.py`.

1. `generate_policy_brief` calls `semantic_search` with the topic.
2. Local mode creates a template-based policy brief using retrieved chunks.
3. OpenAI mode prompts a chat model to write a structured brief from retrieved chunks.
4. Sensitivity is classified by keyword matching over topic and source text.
5. A `Brief` row is inserted.
6. `BriefSource` rows link citation labels to chunk and document IDs.
7. An audit log is written.

Current behavior:

- Briefs are persisted.
- Citation links are persisted by ID.
- The cited evidence text and retrieval scores are not snapshotted.
- Local mode includes generic synthesis language that is not always directly tied to retrieved evidence.
- There is no verification that generated bracket citations align with `BriefSource` rows.

### Review and Export

Review:

1. `/briefs/{brief_id}` returns the brief with live source excerpts.
2. `/briefs/{brief_id}/review` accepts a status from a hardcoded allowed set.
3. The brief review status and reviewer notes are updated.
4. An audit log is written.

Export:

1. `/export/brief/{brief_id}/markdown` calls `export_brief_markdown`.
2. The service builds Markdown from the brief and linked live chunk rows.
3. It writes a file under `exports/`.
4. It returns filename, path, and full Markdown text.
5. An audit log is written.

Current behavior:

- Export writes to local disk from an API route.
- Exported evidence reflects current database chunk text, not necessarily generation-time evidence if chunks ever become editable or versioned.
- The Streamlit review flow is currently blocked by missing `api_patch`.

## Deployment Shape

Local setup is:

1. PostgreSQL/pgvector via Docker Compose.
2. FastAPI via Uvicorn on a manually chosen port.
3. Streamlit on a manually chosen port.

There is no production web server config, container for backend/frontend, authentication, authorization, CORS policy, secrets management, migrations, observability stack, or CI config in this repository.

