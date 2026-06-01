# Demo Script

## Goal

Demonstrate that the app can ingest public AI governance sources, retrieve relevant material, generate a source-grounded answer, create a structured policy brief, and route the brief through review.

## Setup

Start backend and frontend.

Backend:

```bash
cd backend
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload --port 8002
```

Frontend:

```bash
cd frontend
source .venv/bin/activate
API_BASE_URL=http://localhost:8002 python3 -m streamlit run streamlit_app.py --server.port 8502
```

Open:

```text
http://localhost:8502
```

## Demo Steps

### 1. Initialize Database

Go to:

```text
System Status
```

Click:

```text
Initialize database tables
```

### 2. Load Curated Source Pack

Go to:

```text
Source Pack
```

Click:

```text
Load curated sources into Source Library
```

Explain:

> The system begins from a curated approved-source registry rather than arbitrary web scraping.

### 3. Ingest a Source

Select:

```text
NIST AI Risk Management Framework
```

Click:

```text
Ingest selected seed source
```

Explain:

> The app extracts the public page, stores the document, and logs the action.

### 4. Prepare the Document

Go to:

```text
Documents
```

Click:

```text
Check chunk status
Create chunks / check existing chunks
Generate embeddings
```

Explain:

> In local demo mode this prepares searchable chunks without API billing.

### 5. Ask the Knowledge Base

Go to:

```text
Ask Knowledge Base
```

Question:

```text
What is the NIST AI Risk Management Framework?
```

Explain:

> The answer is based on retrieved source chunks and includes source excerpts.

### 6. Generate a Policy Brief

Go to:

```text
Generate Brief
```

Topic:

```text
NIST AI Risk Management Framework and AI governance
```

Click:

```text
Generate policy brief
```

Explain:

> The brief is structured for policy/public diplomacy use and remains a draft.

### 7. Review the Brief

Go to:

```text
Review Briefs
```

Load the brief.

Set status:

```text
reviewed
```

Add reviewer note:

```text
Reviewed for source grounding and policy relevance.
```

Save decision.

Explain:

> This demonstrates human review and governance workflow.

### 8. Check Audit Logs

Go to:

```text
Audit Logs
```

Explain:

> The app records ingestion, chunking, brief generation and review actions.

## Demo Talking Points

- This is not an autonomous publication tool.
- Outputs are draft-only.
- Human review is required before external use.
- Source traceability is central.
- Local mode makes the demo reproducible without API billing.
- OpenAI mode can be enabled for production-like semantic retrieval and synthesis.
