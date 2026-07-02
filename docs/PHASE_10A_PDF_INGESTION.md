# Phase 10A Reliable PDF Ingestion

## 1. Current HTML Ingestion Flow

The current `/ingest/url` route delegates to `backend/app/services/ingestion.py`. The service checks for an exact `Document.url` duplicate, validates `source_id`, calls `trafilatura.fetch_url`, extracts article text and metadata, normalizes text, creates a `Document`, writes an audit log, and assigns the document to a Phase 9A event.

This works for normal HTML pages but assumes the downloaded payload is safe text-like webpage content.

## 2. Root Cause Of The PDF Failure

A direct PDF URL was downloaded as binary content and then treated as ordinary webpage text. The attempted insert included bytes beginning with `%PDF-1.7` and embedded NUL bytes. PostgreSQL rejected the text-column insert because text values cannot contain NUL bytes. The API then exposed a raw SQLAlchemy/PostgreSQL exception, including SQL parameters and part of the binary payload.

## 3. Proposed Content-Type-Aware Ingestion Architecture

Phase 10A adds a binary-safe download and content detection layer:

```text
download bytes with limits
-> inspect HTTP status, content type, magic bytes, and URL suffix
-> PDF path or HTML path
-> extract and sanitize text
-> validate meaningful text
-> create Document
-> assign Event
-> audit successful ingestion
```

HTML ingestion remains supported. PDF ingestion uses bytes and never decodes arbitrary PDF bytes as text.

## 4. PDF Detection Strategy

PDF detection uses:

1. `Content-Type`, including `application/pdf` and parameterized values.
2. `%PDF-` magic bytes, including octet-stream responses.
3. `.pdf` URL suffix only as a fallback when the response is not clearly HTML.

If a `.pdf` URL returns HTML, the response is treated as HTML or an HTML error page, not as a PDF.

## 5. PDF Parsing Library Selection

Use `pypdf` with a constrained dependency. It is lightweight, pure Python, maintained, and adequate for text-based public-sector PDFs. It does not require OCR, Java, system binaries, or external services.

Known limitations:

- image-only/scanned PDFs have no extractable text;
- complex layout and tables may not be reconstructed;
- some CJK PDFs may have imperfect text extraction depending on embedded fonts and ToUnicode maps.

## 6. Text Sanitation Behavior

Before persistence, text fields pass through a reusable sanitizer that:

- removes NUL bytes;
- removes invalid C0 control characters except tab, newline, and carriage return;
- normalizes invalid surrogate characters;
- preserves Japanese, accents, punctuation, and normal Unicode;
- returns predictable strings.

Sanitation is applied to title, raw text, cleaned text, summary, language, topic tags, and derived metadata.

## 7. Title Extraction Behavior

PDF titles use this precedence:

1. usable PDF metadata title;
2. first meaningful heading from extracted text;
3. first meaningful non-empty line;
4. cleaned filename;
5. URL-path fallback.

Unusable metadata titles include blank values, `Untitled`, software placeholders, URL-like strings, control-heavy strings, and overly long values.

## 8. Metadata And Date Extraction Behavior

Published dates use conservative precedence:

1. future explicit user-provided dates, if the API later supports them;
2. reliable PDF metadata creation/modification dates;
3. otherwise `null`.

Phase 10A does not infer dates from arbitrary filename numbers. `fetched_at` remains the normal database timestamp.

## 9. Error And Rollback Behavior

Parsing and validation failures occur before database persistence. Database failures roll back the session. Failed PDF ingestion creates no `Document`, `Event`, `EventDocument`, snapshot, or event brief.

Expected failures return concise API errors without SQL, binary payloads, tracebacks, request parameters, or parser internals.

## 10. Event-Assignment Integration

Successful PDF ingestion still creates a `Document` and passes it through Phase 9A event assignment. Event clustering uses the sanitized title and extracted text, never binary PDF bytes.

No snapshot or event brief is generated automatically.

## 11. Streamlit Error Behavior

The existing frontend error sanitizer is reused. Backend ingestion errors are made concise so Streamlit can show messages such as:

- `This PDF does not contain extractable text. OCR is not supported yet.`
- `Could not parse this PDF.`
- `The downloaded file is too large to ingest.`

No SQL or binary payload should appear in the UI.

## 12. Security And Size Limits

Configurable limits:

- request timeout;
- maximum PDF download size;
- maximum extracted text size;
- maximum public error-message length.

Defaults are conservative for local public-sector demo ingestion and can be adjusted with environment variables.

## 13. Test Plan

Tests cover:

- PDF detection by content type, magic bytes, octet-stream, and parameterized content type;
- `.pdf` URL returning HTML;
- one-page and multi-page text PDFs;
- Japanese Unicode text;
- metadata title, generic title rejection, first-line title, and filename fallback;
- extracted text size limit;
- NUL/control sanitation;
- scanned/image-only, empty, malformed, truncated, encrypted, parser exception, oversized, timeout, non-200, and unsupported content failures;
- successful PDF persistence and event assignment;
- rollback on failure;
- duplicate URL, tracking-parameter clustering, and identical extracted text behavior;
- frontend/API error sanitation;
- HTML ingestion regressions and Phase 9 functionality.

## 14. Manual Verification Plan

1. Start PostgreSQL.
2. Start backend.
3. Start Streamlit.
4. Ingest a normal HTML URL.
5. Confirm HTML behavior is unchanged.
6. Ingest a small text-based English PDF.
7. Confirm readable extracted text and title.
8. Confirm one `Document` and one primary `EventDocument`.
9. Confirm the PDF appears in Events evidence.
10. Ingest the Japanese Digital Agency PDF URL from the issue.
11. Confirm Japanese text is readable and no NUL-byte error appears.
12. Re-ingest the same PDF and confirm duplicate handling.
13. Test a scanned/image-only PDF and confirm OCR-not-supported wording.
14. Test a malformed PDF fixture and confirm no partial records.
15. Confirm Phase 9C snapshot and brief controls still work for PDF-backed events.

## 15. Known Limitations

- No OCR.
- No scanned-PDF text recognition.
- No table reconstruction.
- No chart/image extraction.
- No layout-aware PDF understanding.
- No PDF file storage.
- No signed-document validation.

## 16. OCR And Scanned-PDF Behavior Deferred

Image-only PDFs fail cleanly with an OCR-not-supported message. OCR, scanned-PDF recognition, and image extraction are explicitly deferred to later phases.
