# Setup Guide

This guide runs the project locally in deterministic demo mode. OpenAI configuration is optional.

## Requirements

- Python 3.11+
- Docker Desktop or compatible Docker Compose runtime

## 1. Create a Virtual Environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend and frontend dependencies:

```bash
python3 -m pip install -r backend/requirements.txt
python3 -m pip install -r frontend/requirements.txt
```

## 2. Optional Environment File

The defaults run locally without an API key. If you want to override settings:

```bash
cp .env.example .env
```

Use local deterministic mode unless you have configured a model provider:

```text
EMBEDDING_PROVIDER=local
ANSWER_PROVIDER=local
API_BASE_URL=http://localhost:8002
```

Do not commit `.env`.

## 3. Start PostgreSQL

```bash
docker compose up -d db
```

## 4. Start FastAPI

From a terminal with the virtual environment active:

```bash
cd backend
python3 -m uvicorn app.main:app --reload --port 8002
```

Keep this terminal open.

Swagger is available at:

```text
http://localhost:8002/docs
```

## 5. Initialize Database

Open another terminal from the repository root:

```bash
source .venv/bin/activate
curl -X POST http://localhost:8002/admin/init-db
```

Expected response:

```json
{"status":"ok","message":"Database initialized."}
```

For an existing database created before the event-intelligence migrations, apply the additive SQL files manually before using Events:

```bash
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_0900_phase_9a_events.sql
psql "$DATABASE_URL" -f backend/migrations/versions/20260702_1200_phase_9c_event_snapshots_briefs.sql
```

## 6. Start Streamlit

From the repository root:

```bash
source .venv/bin/activate
python3 -m streamlit run frontend/streamlit_app.py --server.port 8501
```

Open:

```text
http://localhost:8501
```

## 7. Recommended First Workflow

1. System Status: initialize database tables.
2. Source Pack: load curated sources.
3. Source Pack or Ingest URL: ingest an HTML page or text-based PDF.
4. Documents: inspect the document and create chunks if you need search/RAG/document briefs.
5. Admin API, if needed: run event backfill for older documents.
6. Events: inspect event evidence and timeline.
7. Events: create an event snapshot.
8. Events: generate an event brief.
9. Events or review pages: review generated output before use.
10. Audit Logs: check traceability.

Optional event backfill:

```bash
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=true"
curl -X POST "http://localhost:8002/admin/events/backfill?dry_run=false"
```

## Stopping the App

- Press `Control+C` in the backend terminal.
- Press `Control+C` in the frontend terminal.
- Stop PostgreSQL without deleting data:

```bash
docker compose stop db
```
