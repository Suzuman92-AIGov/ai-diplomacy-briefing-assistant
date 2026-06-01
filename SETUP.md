# Setup Guide

This guide runs the project locally in **local demo mode**, without OpenAI API billing.

## Requirements

Install:

- Python 3.11+
- Docker Desktop
- VS Code or another code editor

## 1. Create local environment file

From the project root:

```bash
cp .env.example .env
```

In `.env`, use:

```text
EMBEDDING_PROVIDER=local
ANSWER_PROVIDER=local
API_BASE_URL=http://localhost:8002
OPENAI_API_KEY=your_api_key_here
```

You do **not** need a real OpenAI API key in local mode.

## 2. Start database

```bash
docker rm -f ai_diplomacy_pgvector || true
docker compose up -d db
```

## 3. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8002
```

Keep this terminal open.

## 4. Initialize database

Open a new terminal:

```bash
curl -X POST http://localhost:8002/admin/init-db
```

Expected response:

```json
{"status":"ok","message":"Database initialized."}
```

## 5. Start frontend

Open another terminal:

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
API_BASE_URL=http://localhost:8002 python3 -m streamlit run streamlit_app.py --server.port 8502
```

Open:

```text
http://localhost:8502
```

## Recommended Demo Flow

1. Start Here → Run demo setup
2. Documents → Create chunks / check existing chunks
3. Documents → Generate embeddings / prepare searchable representations
4. Ask Knowledge Base → ask a source-grounded question
5. Generate Brief → create a structured policy brief
6. Review Briefs → update review status
7. Export Brief → export as Markdown
8. Dashboard → show updated metrics
9. Audit Logs → show traceability

## Stopping the App

When finished:

- press `Control + C` in the backend terminal;
- press `Control + C` in the frontend terminal.

Docker database can remain running, or you can stop it with:

```bash
docker compose down
```
