# GitHub Release Draft: v0.10.0

## Release Title

```text
v0.10.0 - Event Intelligence and Reliable PDF Ingestion
```

## Release Body

```markdown
## Overview

v0.10.0 presents AI Diplomacy Briefing Assistant as an evidence-first event-intelligence prototype for policy and media monitoring.

The application now goes beyond isolated article summaries: it preserves original source documents as evidence, groups related documents into events, captures event snapshots, detects changes between event states, and generates reviewable event briefs.

This is a functional local prototype and advanced proof of concept. It is not production-ready.

## Highlights

- Event-oriented intelligence layer over the document evidence store.
- Events UI with filtering, event detail, source/publisher coverage, and evidence timeline.
- Immutable event snapshots.
- Deterministic snapshot comparison and change levels.
- Event-level brief generation from snapshot evidence.
- Deterministic fallback when no model provider is configured.
- Event-brief review workflow.
- Text-based PDF ingestion through a binary-safe `pypdf` path.
- Japanese/Unicode preservation and NUL/control-character sanitation.
- Existing search, RAG, document-level briefs, Markdown export, dashboard, and audit logs remain available.

## Architecture Progression

Earlier versions focused on source-grounded document retrieval and document-level briefing. v0.10.0 documents the current event-intelligence architecture:

```text
Source -> Document -> Event -> Event Snapshot -> Change Detection -> Event Brief -> Review
```

Original documents remain the evidence layer. Event snapshots and briefs are derived from those documents and should be reviewed before use.

## Verified Capabilities

- HTML ingestion.
- Text-based PDF ingestion.
- Source registry and curated seed sources.
- Document chunking.
- Local TF-IDF search and optional OpenAI/pgvector retrieval.
- RAG answers over source chunks.
- Document-level policy briefs and review.
- Markdown export and audit logging.
- Deterministic event clustering by URL/content/title/similarity.
- Evidence timelines.
- Event snapshots and deterministic change detection.
- Event briefs with deterministic fallback and optional LLM-assisted wording.
- Automated pytest coverage for core event, ingestion, source, review, and frontend helper behavior.

## Local Setup

Run locally with PostgreSQL, FastAPI, and Streamlit:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r backend/requirements.txt
python3 -m pip install -r frontend/requirements.txt
docker compose up -d db
cd backend
python3 -m uvicorn app.main:app --reload --port 8002
```

In another terminal from the repository root:

```bash
source .venv/bin/activate
python3 -m streamlit run frontend/streamlit_app.py --server.port 8501
```

Open:

- Swagger: `http://localhost:8002/docs`
- Streamlit: `http://localhost:8501`

Initialize the database:

```bash
curl -X POST http://localhost:8002/admin/init-db
```

## Test Status

Run:

```bash
pytest
python3 -m compileall backend/app frontend tests
git diff --check
```

See the repository completion report for the exact local run result.

## Known Limitations

- No OCR or scanned-PDF text recognition.
- No scheduled monitoring or alerts.
- No authentication, authorization, or multi-tenant access control.
- No manual event merge/delete workflow.
- No source-independence verification.
- Local TF-IDF retrieval is deterministic but limited.
- Model-assisted output depends on provider configuration and should be reviewed.
- No production deployment hardening or security certification.
- FastAPI application metadata still reports an older internal API version because this is a documentation-only release.
```

## Repository Presentation Suggestions

Suggested repository description:

```text
Evidence-first event intelligence prototype for AI governance and policy monitoring, with FastAPI, Streamlit, PostgreSQL, source-grounded RAG, snapshots, change detection, event briefs, and text-PDF ingestion.
```

Suggested topics:

```text
event-intelligence
media-intelligence
ai-governance
public-policy
foreign-policy
public-diplomacy
rag
fastapi
streamlit
postgresql
pgvector
responsible-ai
pdf-ingestion
```

Suggested project status wording:

```text
Functional local prototype and advanced proof of concept; not production-ready.
```

Do not add badges unless the linked workflow or service exists. Do not create the release remotely, push tags, or change repository settings as part of this documentation release.
