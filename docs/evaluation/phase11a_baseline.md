# Phase 11A Event Clustering Baseline

- Split: `all`
- Benchmark documents: `37`
- Gold event groups: `18`
- Languages: `{"English": 31, "Japanese": 5, "missing": 1}`
- Thresholds: title `0.92`, semantic `0.78`, window `14` days
- Production database: not used; isolated sqlite:///:memory:

## Duplicate Detection

- Precision: `1.0`; recall: `1.0`; F1: `1.0`
- False positives: `0`
- False negatives: `0`

## Event Clustering

- Precision: `0.833333`; recall: `0.142857`; F1: `0.243902`
- B-cubed F1: `0.734637`
- Adjusted Rand Index: `0.232091`
- Pairwise false positives: `1`
- Pairwise false negatives: `30`

## Product Metrics

- False merge rate: `0.166667`
- False split rate: `0.857143`
- Perfect event percentage: `0.5`
- Cross-language match accuracy: `0.0` over `14` pairs
- Japanese-title match accuracy: `0.0` over `3` pairs
- Recurring-title separation accuracy: `1.0` over `5` pairs
- Hard-negative accuracy: `0.996109` over `257` pairs

## Metadata Quality

- Flagged documents: `5`
- Flag counts: `{"URL-path-like title": 1, "implausible publication date": 3, "missing publisher when source exists": 1, "missing source": 1, "missing title": 1, "publication date later than fetched date": 1, "unsupported or missing language": 1}`

## Threshold Sweep

- Best development config: title `0.85`, semantic `0.65`, window `7` days
- Best development pairwise F1: `0.518519`
- Held-out test pairwise F1: `0.0`
- Held-out test false merges: `0`
- Held-out test false splits: `1`

Top threshold rows by development F1:

| title | semantic | window_days | pairwise_f1 | precision | recall | false_merges | false_splits |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.85 | 0.65 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.85 | 0.7 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.9 | 0.65 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.92 | 0.65 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.95 | 0.65 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.97 | 0.65 | 7 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.85 | 0.65 | 14 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.85 | 0.7 | 14 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.9 | 0.65 | 14 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
| 0.92 | 0.65 | 14 | 0.518519 | 0.875 | 0.368421 | 1 | 12 |
