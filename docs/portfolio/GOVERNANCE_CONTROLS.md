# Governance Controls

> Portfolio note: this document describes governance concepts for the local prototype. The current v0.10.0 event-intelligence overview is in the root [README](../../README.md).

## 1. Approved Source Registry

The system starts from curated sources rather than arbitrary web content.

Each source has:

- source type
- reliability tier
- institution/country
- notes
- topic tags

## 2. Source Reliability Tiers

Reliability tiers help distinguish:

- official institutional sources;
- think tank analysis;
- media reporting;
- company/self-interested sources;
- other sources.

## 3. Public Sources Only

The prototype is designed for public-source material. It should not ingest confidential, classified or private documents.

## 4. No Source, No Claim

The assistant should not generate claims that cannot be traced to retrieved source material.

## 5. Draft-only Output

Generated answers and briefs are treated as drafts.

They are not official positions and should not be published without human review.

## 6. Human Review Workflow

Briefs move through review statuses:

```text
draft
reviewed
approved
rejected
needs_senior_review
```

## 7. Senior Review Escalation

Sensitive topics can be marked as requiring senior review.

Examples:

- national security
- military AI
- surveillance
- sanctions
- export controls
- election interference
- active geopolitical disputes
- crisis communication

## 8. Audit Logs

The system logs important actions:

- loading source pack
- ingesting URLs
- chunking documents
- preparing searchable chunks
- generating briefs
- changing review status

## 9. Citation Preservation

Briefs preserve references to source chunks through `brief_sources`.

This helps maintain traceability between generated outputs and source evidence.

## 10. Local and Production Modes

Local mode supports reproducible testing without external API billing.

Production-like mode can use external embeddings and LLMs, subject to vendor review and data governance controls.
