# Phase 11A Real-World Event Clustering Evaluation

Phase 11A adds a reproducible benchmark and command-line evaluator for the existing event clustering pipeline. It measures current behavior before introducing major new clustering algorithms or changing production defaults.

## Current Clustering Pipeline

Documents remain the evidence layer. Event assignment happens after a document has been persisted and uses helpers in `backend/app/services/events.py`.

Current deterministic and approximate checks run in this order:

1. Exact canonical URL match against existing `Document.url`.
2. Normalized URL match, where tracking parameters and fragments are removed.
3. Normalized content hash match over cleaned text.
4. Near-duplicate title match against existing events inside the event title match window.
5. TF-IDF character n-gram similarity over document title, summary, and topic tags against event title and summary inside the same time window.
6. New event creation when no candidate satisfies the configured thresholds.

Current configurable thresholds:

- `EVENT_NEAR_DUPLICATE_TITLE_THRESHOLD`: `0.92`
- `EVENT_SEMANTIC_SIMILARITY_THRESHOLD`: `0.78`
- `EVENT_TITLE_MATCH_WINDOW_DAYS`: `14`

The evaluator imports and calls the production normalization, duplicate detection, title similarity, semantic similarity, and assignment helpers. It does not reimplement clustering logic.

## Known Failure Modes

- Cross-language English/Japanese reports may split because character n-grams are not true multilingual semantics.
- Similar recurring government titles can merge when dates are too close or metadata is missing.
- Similar policy topics can merge when title or summary wording is close but events differ.
- Identical or near-identical titles on different dates depend heavily on the title match window.
- URL normalization cannot detect syndication, copied articles, or canonical tags not present in the stored URL.
- Content hash detection only catches exact normalized text matches.
- Metadata gaps can weaken clustering and make error analysis less certain.

## Benchmark Structure

The benchmark is stored as JSONL at `tests/fixtures/event_clustering_benchmark.jsonl`. Each line is one document fixture with:

- `benchmark_document_id`
- `event_label`
- `language`
- `title`
- `summary`
- `canonical_url`
- `source_name`
- `publisher`
- `published_date`
- `expected_duplicate_group`
- `notes`
- `split`

Additional optional fields are supported for evaluation metadata:

- `evaluation_tags`: labels such as `hard_negative`, `cross_language`, `recurring_title`, and `japanese_title`.
- `synthetic`: must be `true` for repository fixtures.

Fixtures use short synthetic excerpts or factual summaries only. They do not include copyrighted full articles and do not depend on live websites.

## Labeling Rules

`event_label` is the gold real-world event. Documents share a label only when they describe the same concrete development, not merely the same topic.

`expected_duplicate_group` is used only for document duplicate evaluation. It should be present when documents are exact or near-identical evidence records, such as tracking-parameter URL variants or identical content under different URLs. It must not be used for ordinary multi-source coverage of the same event.

Uncertain examples must be labeled in `notes` and should not be counted as correct by implication. If the benchmark cannot justify a same-event label from the fixture text, it should be split into separate events.

## Development/Test Split

The development split is used for error analysis and threshold sweeps. The test split is held out for one evaluation of the selected configuration after the development sweep.

The committed fixture is compact, so test-set conclusions are directional rather than performance claims. It is meant to make regressions visible and guide future benchmark growth.

## Metrics

Duplicate detection:

- Precision: predicted duplicate pairs that are gold duplicate pairs.
- Recall: gold duplicate pairs found by production duplicate checks.
- F1: harmonic mean of precision and recall.
- False positives and false negatives.

Event clustering:

- Pairwise precision: predicted same-event document pairs that share a gold event label.
- Pairwise recall: gold same-event document pairs predicted in the same event.
- Pairwise F1.
- B-cubed precision/recall/F1: per-document cluster overlap averaged across documents.
- Adjusted Rand Index: supplementary clustering agreement metric.

Product-relevant metrics:

- False merge rate: false same-event pairs divided by predicted same-event pairs.
- False split rate: missed same-event pairs divided by gold same-event pairs.
- Perfect event percentage: gold events whose predicted cluster exactly equals the gold document set.
- Cross-language match accuracy: same-event English/Japanese pairs predicted together.
- Japanese-title match accuracy: same-event Japanese/Japanese pairs predicted together.
- Recurring-title separation accuracy: recurring-title hard negative pairs predicted apart.
- Hard-negative accuracy: hard-negative pairs predicted apart.

No single score should be reported without error counts and examples.

## Error Analysis Workflow

The evaluator produces a Markdown error table and JSON details with:

- document IDs;
- gold event labels;
- predicted event labels;
- similarity score;
- clustering method;
- relevant threshold;
- error category;
- short explanation.

Readable categories include:

- URL normalization failure;
- duplicate-content failure;
- false title match;
- false semantic match;
- cross-language false split;
- recurring-title false merge;
- date-window failure;
- missing metadata;
- source or publisher mismatch;
- low-confidence new-event creation;
- other.

False merges and false splits should be reviewed before changing thresholds. Metadata flags should be reviewed separately because poor title, date, source, publisher, or language quality can make clustering failures appear algorithmic.

## Threshold-Tuning Policy

Phase 11A may sweep development-set thresholds but does not automatically change production defaults.

Documented sweep ranges:

- near-duplicate title threshold: `0.85`, `0.90`, `0.92`, `0.95`, `0.97`
- semantic title/summary threshold: `0.65`, `0.70`, `0.78`, `0.85`, `0.90`
- event title match window: `7`, `14`, `30`, `90` days

The selected configuration is the best development configuration by pairwise event F1, with false merge count used as a tie-breaker. It is then evaluated once on the held-out test split.

Production defaults should change only in a later phase or in a small configuration-only change with clear improvement, documented trade-offs, and regression tests. The final test split must not be repeatedly tuned against.

## Reproducibility Requirements

- The fixture is repository-contained.
- The evaluator runs against an isolated SQLite database created for the run.
- The evaluator never connects to or writes to the configured production database.
- Document IDs are assigned deterministically by fixture order.
- A fixed fetched timestamp is used for metadata checks.
- Reports are generated from deterministic fixture data.
- The command can emit JSON and Markdown output.

Example command from the repository root:

```bash
PYTHONPATH=backend python3 -m app.evaluation.event_clustering \
  --dataset tests/fixtures/event_clustering_benchmark.jsonl \
  --json-report docs/evaluation/phase11a_baseline.json \
  --markdown-report docs/evaluation/phase11a_baseline.md \
  --error-report docs/evaluation/phase11a_errors.md \
  --sweep
```

## Manual Verification

1. Run the full evaluation with the command above.
2. Inspect baseline metrics in `docs/evaluation/phase11a_baseline.md`.
3. Inspect false merges in `docs/evaluation/phase11a_errors.md`.
4. Inspect false splits in the same error report.
5. Run a development threshold sweep with `--sweep`.
6. Confirm the selected development configuration is evaluated once on `split=test`.
7. Confirm production data was not modified by noting the evaluator uses an isolated SQLite database and by checking application database state separately if needed.
8. Add a new benchmark case as one JSONL line with a unique `benchmark_document_id`, a justified `event_label`, a `split`, and `synthetic: true`.
9. Rerun the report and compare deterministic JSON/Markdown output.

## Limitations

The initial fixture is intentionally compact. It exercises architecture and failure modes, but it is not a statistically representative public benchmark. It does not include live pages, full copyrighted articles, OCR output, manual analyst adjudication tooling, or multilingual embeddings.

The current character n-gram TF-IDF approach may connect some Japanese variants but does not provide reliable English/Japanese semantic matching. If cross-language false splits remain prominent, Phase 11B should evaluate translation or multilingual embeddings with explicit evidence that they improve held-out performance without increasing false merges.
