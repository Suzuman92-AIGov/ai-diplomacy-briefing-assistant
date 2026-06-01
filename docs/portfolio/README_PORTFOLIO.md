# AI Diplomacy Briefing Assistant

A RAG-style policy briefing assistant for monitoring public-source developments in AI governance, foreign policy, digital policy and public diplomacy.

## Project Summary

The **AI Diplomacy Briefing Assistant** is a portfolio-grade prototype designed for public diplomacy, policy, embassy, think tank and international affairs teams. It ingests curated public sources, stores documents, chunks source material, retrieves relevant passages, generates source-grounded answers, produces structured policy briefs, and routes outputs through a review workflow with audit logging.

The project is designed not as an autonomous publisher, but as a responsible AI assistant for internal briefing and analysis.

## Core Use Case

A public diplomacy or policy team needs to follow international developments related to:

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
6. keep draft outputs under human review;
7. preserve citations and audit logs.

## What the Prototype Demonstrates

This project demonstrates both technical and governance competence:

- FastAPI backend
- Streamlit frontend
- PostgreSQL + pgvector
- URL ingestion
- article extraction
- document storage
- chunking
- local retrieval mode
- optional OpenAI embeddings / LLM mode
- source-grounded Q&A
- structured policy brief generation
- review workflow
- audit logging
- curated approved-source registry
- source reliability tiers
- citation preservation

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
Audit log
```

## Main Features

### 1. Curated Source Pack

The system includes a curated source pack with official and analytical sources such as:

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

Each source includes metadata such as:

- source type
- reliability tier
- country/institution
- topic tags
- sensitivity level
- notes

### 2. URL Ingestion

Users can ingest public URLs. The system extracts the main page text, cleans it, stores document metadata, and creates an audit log entry.

### 3. Chunking and Retrieval

Documents are split into searchable chunks. The app supports:

- local TF-IDF retrieval for reproducible portfolio testing;
- optional OpenAI embeddings + pgvector mode for production-like architecture.

### 4. Ask Knowledge Base

Users can ask questions over the ingested source base. The system retrieves relevant chunks and generates a source-grounded answer.

### 5. Generate Brief

The system generates structured policy briefs with:

- Executive Summary
- Key Developments / Source Findings
- Why It Matters
- Foreign Policy Relevance
- Risk / Opportunity
- Sensitivity Level
- Suggested Public Diplomacy Angle
- Sources Used
- Governance Note

### 6. Review Workflow

Generated briefs are saved as drafts and can be reviewed through a governance workflow:

```text
draft → reviewed → approved / rejected / needs_senior_review
```

Reviewer notes and status changes are logged.

### 7. Audit Logs

The system logs key actions such as:

- source pack loading
- URL ingestion
- chunking
- embedding/search preparation
- brief generation
- review status updates

## Local and Production-like Modes

The app supports two modes.

### Local Demo Mode

```text
EMBEDDING_PROVIDER=local
ANSWER_PROVIDER=local
```

This mode requires no OpenAI API billing and is useful for portfolio demonstrations.

### Production-like Mode

```text
EMBEDDING_PROVIDER=openai
ANSWER_PROVIDER=openai
```

This mode uses OpenAI embeddings and LLM answer generation when API billing is available.

## Responsible AI Design Principles

The project is built around practical AI governance principles:

1. No source, no claim.
2. Public sources only.
3. AI output is a draft, not an official position.
4. Human review before external use.
5. Sensitive topics require senior review.
6. Source reliability must be visible.
7. Audit logs should record important actions.
8. Brief citations should remain stable.
9. Official sources should be prioritized over commentary.
10. The system should separate retrieved evidence from generated analysis.

## Suggested Demo Flow

1. Start backend and frontend.
2. Initialize database.
3. Load curated source pack.
4. Ingest selected seed source.
5. Create chunks.
6. Prepare searchable chunks.
7. Ask a question over the knowledge base.
8. Generate a policy brief.
9. Review the brief and change status.
10. Check audit logs.

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

## Portfolio Value

This project is designed to show the ability to connect:

- AI application architecture;
- public diplomacy and policy use cases;
- responsible AI governance;
- source-grounded retrieval;
- structured briefing workflows;
- human review controls.

It is especially relevant for roles in:

- AI governance
- public policy
- digital policy
- embassy/public diplomacy work
- think tanks
- international organizations
- technology policy consulting
- responsible AI program support
