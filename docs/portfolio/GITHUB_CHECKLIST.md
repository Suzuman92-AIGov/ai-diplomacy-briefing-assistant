# GitHub Portfolio Checklist

## Required Before Publishing

- [ ] Remove all `.env` files.
- [ ] Keep only `.env.example`.
- [ ] Confirm no API keys are committed.
- [ ] Add screenshots.
- [ ] Add README.
- [ ] Add case study.
- [ ] Add architecture diagram.
- [ ] Add demo script.
- [ ] Add governance docs.
- [ ] Add clear setup instructions.
- [ ] Add local mode instructions.
- [ ] Add limitations section.
- [ ] Add future improvements section.

## Recommended Screenshots

1. Home / System Status
2. Source Pack
3. Sources
4. Ingest URL
5. Documents with chunk status
6. Ask Knowledge Base
7. Generate Brief
8. Review Briefs
9. Audit Logs

## Repository Structure

```text
ai-diplomacy-briefing-assistant/
  backend/
  frontend/
  docs/
  data/
  README.md
  CASE_STUDY.md
  ARCHITECTURE.md
  DEMO_SCRIPT.md
  .env.example
  docker-compose.yml
```

## Security Notes

Never commit:

```text
.env
OPENAI_API_KEY
database passwords beyond local demo defaults
personal credentials
```

## Suggested GitHub Description

RAG-style AI governance and foreign policy briefing assistant with curated public-source ingestion, source-grounded answers, structured policy brief generation, human review workflow and audit logging.

## Suggested GitHub Topics

```text
rag
ai-governance
public-policy
foreign-policy
public-diplomacy
fastapi
streamlit
postgresql
pgvector
responsible-ai
```
