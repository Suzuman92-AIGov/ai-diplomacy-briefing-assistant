# AI Diplomacy Briefing Assistant

**Phase 9 Demo Polish Edition**

A RAG-style policy briefing assistant for monitoring public-source developments in AI governance, foreign policy, digital policy and public diplomacy.

The project is designed as a responsible AI prototype for internal policy/public diplomacy workflows. It ingests curated public sources, retrieves relevant source chunks, generates source-grounded answers, produces structured policy briefs, supports human review, exports briefs as Markdown, and keeps audit logs.

## Quickstart

See [SETUP.md](SETUP.md) for local setup instructions.

Local demo mode works without OpenAI API billing:

```text
EMBEDDING_PROVIDER=local
ANSWER_PROVIDER=local
```

## What This Project Demonstrates

- practical RAG application design
- source governance
- curated approved-source registry
- source reliability tiers
- public-source ingestion
- document chunking
- local retrieval mode
- source-grounded Q&A
- structured policy brief generation
- human review workflow
- audit logging
- Markdown export
- operational dashboard
- non-technical demo guidance

## Core Use Case

A public diplomacy or policy team needs to monitor international developments related to:

- AI governance
- AI regulation
- AI safety
- responsible AI
- digital policy
- international standard-setting
- Japan / EU / US / OECD / G7 AI policy
- AI and foreign policy

The assistant helps the team:

1. maintain an approved source registry;
2. ingest public-source material;
3. search across source chunks;
4. ask questions over the knowledge base;
5. generate structured policy briefs;
6. route outputs through human review;
7. preserve citations and audit logs.

## Main Features

### Start Here

A guided onboarding page for demo users. It explains the workflow and provides a demo setup helper.

### Dashboard

Operational overview of:

- total sources
- documents
- chunks
- searchable chunks
- generated briefs
- audit logs
- sources by reliability tier
- sources by type
- documents by sensitivity
- briefs by review status
- recent audit activity

### Curated Source Pack

The app includes a seed source pack with policy-relevant sources such as:

- NIST AI Risk Management Framework
- OECD AI Principles
- European Commission AI Act
- European AI Office
- Council of Europe AI Convention
- UNESCO AI Ethics Recommendation
- G7 Hiroshima AI Process
- UK AI Safety Institute
- Japan Cabinet Office AI Strategy
- METI AI Governance
- White House AI Executive Order
- CSET
- CSIS
- Brookings

Each source includes metadata:

- source type
- reliability tier
- country/institution
- topic tags
- sensitivity level
- notes

### Batch Ingestion

Users can select multiple seed sources and ingest them in one run. The app reports per-source success or failure instead of failing silently.

### Documents and Chunking

Ingested pages are stored as documents and split into searchable chunks. Existing chunks are preserved to protect citation integrity.

### Ask Knowledge Base

Users can ask questions over the ingested knowledge base and receive source-grounded answers.

### Generate Brief

The app generates structured policy briefs with sections such as:

- Executive Summary
- Key Developments / Source Findings
- Why It Matters
- Foreign Policy Relevance
- Evidence Strength
- Risk / Opportunity
- Sensitivity Level
- Suggested Internal Use
- Suggested Public Diplomacy Angle
- Sources Used
- Governance Note

### Review Briefs

Generated briefs move through a review workflow:

```text
draft → reviewed → approved / rejected / needs_senior_review
```

### Export Brief

Generated briefs can be exported as Markdown deliverables with metadata, review status, sources, excerpts and a governance disclaimer.

### Audit Logs

The app records important actions such as:

- source pack loading
- URL ingestion
- chunking
- searchable representation preparation
- brief generation
- review status changes
- Markdown export

## Architecture

```text
Curated public sources
        ↓
Approved source registry
        ↓
URL ingestion
        ↓
Article extraction and cleaning
        ↓
Document storage
        ↓
Chunking
        ↓
Local retrieval or OpenAI embeddings
        ↓
Ask Knowledge Base
        ↓
Generate Policy Brief
        ↓
Human review workflow
        ↓
Markdown export / audit logs
```

## Local and Production-like Modes

### Local Demo Mode

```text
EMBEDDING_PROVIDER=local
ANSWER_PROVIDER=local
```

This mode requires no OpenAI API billing and is useful for reproducible portfolio demonstrations.

### Production-like Mode

```text
EMBEDDING_PROVIDER=openai
ANSWER_PROVIDER=openai
```

This mode can use OpenAI embeddings and LLM answer generation when API billing is available.

## Responsible AI Design Principles

1. No source, no claim.
2. Public sources only.
3. AI output is a draft, not an official position.
4. Human review before external use.
5. Sensitive topics require senior review.
6. Source reliability must be visible.
7. Audit logs should record important actions.
8. Brief citations should remain stable.
9. Official sources should be prioritized over commentary.
10. Retrieved evidence should be separated from generated synthesis.

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

## Example Questions

```text
What is the NIST AI Risk Management Framework?
What are the main functions of the AI RMF?
How does the EU AI Act use a risk-based approach?
Why does AI governance matter for public diplomacy?
What are the foreign policy implications of international AI standards?
```

## Example Brief Topics

```text
NIST AI Risk Management Framework and AI governance
EU AI Act risk-based AI regulation
G7 Hiroshima AI Process and international AI governance
AI governance and public diplomacy
Responsible AI as a foreign policy issue
```

## Documentation

Additional documentation is available in [`docs/`](docs/README.md), including:

- case study
- architecture explanation
- demo script
- governance controls
- GitHub publishing checklist

## Limitations

This is a prototype. Current limitations include:

- Local TF-IDF retrieval is less powerful than production-grade embeddings.
- Some websites may block extraction or return incomplete text.
- There is no authentication or role-based access control yet.
- Scheduled ingestion is not yet implemented.
- OpenAI mode requires separate API billing.
- The app is currently optimized for local demo use.

## Future Improvements

Potential next steps:

- deployment-friendly Streamlit demo edition;
- screenshots and demo video;
- PDF export;
- authentication and roles;
- scheduled source monitoring;
- source freshness filters;
- better sensitivity classifier;
- evaluation dataset for retrieval quality;
- cloud deployment guide.
