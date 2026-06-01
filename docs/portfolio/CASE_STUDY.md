# Case Study: Building an AI Diplomacy Briefing Assistant

## 1. Problem

Public diplomacy and policy teams increasingly need to monitor fast-moving developments in AI governance, AI regulation, digital policy and international technology competition.

However, several problems appear:

- AI policy information is fragmented across governments, international organizations, think tanks and media.
- Teams need quick summaries but cannot rely on unsupported AI-generated claims.
- Sensitive topics require human review.
- Source reliability matters.
- Official positions must not be confused with commentary.
- Generated outputs should be draft-only until reviewed.

The project addresses this by creating a responsible RAG-style briefing assistant.

## 2. Solution

I built a prototype called **AI Diplomacy Briefing Assistant**.

The system ingests curated public sources, chunks them into searchable passages, retrieves relevant material, generates source-grounded answers, and produces structured policy briefs. It also includes a review workflow and audit logs.

The goal is not to automate official communication. The goal is to support internal monitoring, drafting and review.

## 3. Design Philosophy

The project is built around a simple governance principle:

> AI should assist briefing work, but source traceability and human review must remain central.

This shaped several design decisions:

- The system starts from curated approved sources.
- Each source has a reliability tier.
- AI-generated outputs are treated as drafts.
- Briefs move through a review workflow.
- Sensitive topics can be escalated.
- Audit logs record major system actions.
- Citations are preserved.

## 4. Architecture

```text
Curated source pack
        ↓
Source registry
        ↓
URL ingestion
        ↓
Document storage
        ↓
Chunking
        ↓
Retrieval
        ↓
Source-grounded answer
        ↓
Policy brief generation
        ↓
Human review workflow
        ↓
Audit log
```

## 5. Technology Stack

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector
- Pydantic

### Frontend

- Streamlit

### Data / Retrieval

- URL extraction
- document cleaning
- chunking
- local TF-IDF retrieval for demo mode
- optional OpenAI embeddings + pgvector mode

### Governance Layer

- source reliability tiers
- sensitivity levels
- review statuses
- reviewer notes
- audit logs
- citation trail

## 6. Main Features

### Curated Source Pack

The system includes approved seed sources from institutions such as:

- NIST
- OECD
- European Commission
- UNESCO
- Council of Europe
- G7 / Japan MOFA
- METI
- UK AI Safety Institute
- White House
- CSET
- CSIS
- Brookings

### Ask Knowledge Base

Users can ask questions over the ingested source base. The system retrieves relevant chunks and generates a grounded answer.

### Generate Brief

The system creates structured policy briefs with sections designed for policy/public diplomacy teams.

### Review Briefs

Generated briefs enter a governance workflow:

```text
draft → reviewed → approved / rejected / needs_senior_review
```

### Audit Logs

The system records major actions such as ingestion, chunking, brief generation and review status changes.

## 7. Responsible AI Controls

| Risk | Control |
|---|---|
| Hallucination | Source-grounded retrieval and citations |
| Unsupported claims | No-source-no-claim principle |
| Source bias | Source type and reliability tiers |
| Sensitive topics | Sensitivity classification and senior review option |
| Over-automation | Draft-only outputs |
| Lack of accountability | Audit logs |
| Citation instability | Citation-safe chunking |

## 8. What I Learned

This project helped connect practical AI engineering with policy and governance thinking.

Key lessons:

- RAG is not only a technical pattern; it is also a governance tool.
- Source quality and source metadata matter as much as model output.
- Human review should be designed into the workflow, not added later.
- Local demo modes are useful for reproducibility and portfolio evaluation.
- A useful AI governance prototype should demonstrate controls, not only generation.

## 9. Limitations

The current version is a prototype.

Limitations include:

- Local TF-IDF retrieval is less powerful than production-grade embeddings.
- Some websites may block extraction or return incomplete text.
- The current review system is simplified.
- There is no authentication or role-based access control yet.
- Scheduled ingestion is not yet implemented.
- Brief quality is stronger in OpenAI mode than in local extractive mode.

## 10. Future Improvements

Potential next steps:

- scheduled source monitoring;
- RSS ingestion;
- batch ingestion of stable sources;
- role-based access control;
- export brief to Markdown/PDF;
- better sensitivity classifier;
- evaluation dataset;
- prompt-injection checks;
- source freshness filters;
- deployment to cloud;
- polished dashboard analytics;
- multi-language source handling.

## 11. Portfolio Summary

This project shows that I can design a practical AI governance workflow around a RAG-style system, combining technical implementation with policy-oriented use cases and responsible AI controls.
