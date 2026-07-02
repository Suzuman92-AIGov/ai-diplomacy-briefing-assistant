# Project Instructions

## Product goal

Build an evidence-first multilingual media intelligence application.

The product must help users understand:

1. What happened
2. What changed
3. Why it matters
4. Which sources support the conclusion
5. Where sources disagree

## Engineering rules

- Do not make unrelated changes.
- Inspect existing code before creating new abstractions.
- Preserve backward compatibility unless explicitly approved.
- Use database migrations for schema changes.
- Add tests for every bug fix and new service.
- Do not silently catch exceptions.
- Use structured logging.

- Keep the application focused on evidence-based diplomacy and media briefing.
- Preserve source traceability for every generated brief.
- Distinguish source evidence from AI-generated analysis.
- Do not present unsupported policy claims as facts.
- Preserve local/offline demo mode unless explicitly changing it.
- Keep backend and frontend configuration consistent.
- Every factual briefing claim must reference one or more source records.
- 
- Run the complete test suite before finishing.

## Required completion report

For each task, report:

- Files changed
- Database migrations added
- Tests added
- Commands run
- Test results
- Unresolved risks
