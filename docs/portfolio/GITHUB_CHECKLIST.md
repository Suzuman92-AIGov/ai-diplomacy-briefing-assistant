# GitHub Portfolio Checklist

> Historical checklist note: this checklist predates the v0.10.0 documentation release. For current repository presentation suggestions, see [docs/GITHUB_RELEASE_V0.10.0.md](../GITHUB_RELEASE_V0.10.0.md).

## Required Before Publishing

- [ ] Remove all `.env` files.
- [ ] Keep only `.env.example`.
- [ ] Confirm no API keys are committed.
- [ ] Refresh v0.10.0 screenshots using [the screenshot checklist](../screenshots/V0_10_SCREENSHOT_CHECKLIST.md).
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

1. Dashboard
2. Events overview
3. Event detail
4. Evidence timeline
5. Event Intelligence snapshot/change section
6. Event brief
7. PDF ingestion success
8. Search or RAG
9. Audit Logs

## Repository Structure

```text
ai-diplomacy-briefing-assistant/
  backend/
  frontend/
  docs/
  data/
  README.md
  SETUP.md
  CHANGELOG.md
  .env.example
  docker-compose.yml
```

## Security Notes

Never commit:

```text
.env
API keys
database credentials
personal credentials
```

## Suggested GitHub Description

Evidence-first event intelligence prototype for AI governance and policy monitoring, with source-grounded RAG, snapshots, change detection, event briefs and text-PDF ingestion.

## Suggested GitHub Topics

```text
rag
event-intelligence
media-intelligence
ai-governance
public-policy
foreign-policy
public-diplomacy
fastapi
streamlit
postgresql
pgvector
responsible-ai
pdf-ingestion
```
