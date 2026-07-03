from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.evaluation import event_clustering as evaluator
from app.evaluation.event_clustering import (
    BenchmarkDocument,
    ThresholdConfig,
    calculate_clustering_metrics,
    calculate_duplicate_metrics,
    calculate_metadata_quality,
    calculate_product_metrics,
    categorize_errors,
    evaluate_documents,
    load_benchmark,
    render_markdown_errors,
    render_markdown_summary,
    result_to_dict,
    split_documents,
    sweep_thresholds,
)
from app.services.events import assign_document_to_event as production_assign_document_to_event


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "event_clustering_benchmark.jsonl"


def make_doc(
    document_id: str,
    event_label: str,
    *,
    title: str | None = None,
    split: str = "development",
    language: str = "English",
    duplicate_group: str = "",
    tags: tuple[str, ...] = (),
) -> BenchmarkDocument:
    return BenchmarkDocument(
        benchmark_document_id=document_id,
        event_label=event_label,
        language=language,
        title=title if title is not None else f"{event_label} title",
        summary=f"Synthetic fixture: {event_label} short summary.",
        canonical_url=f"https://fixtures.example/{document_id}",
        source_name="Test Source",
        publisher="Test Source",
        published_date=None,
        expected_duplicate_group=duplicate_group,
        notes="Synthetic unit-test fixture.",
        split=split,
        evaluation_tags=tags,
        synthetic=True,
    )


def test_benchmark_fixture_validation_and_composition():
    documents = load_benchmark(FIXTURE_PATH)

    assert 30 <= len(documents) <= 50
    assert {doc.split for doc in documents} == {"development", "test"}
    assert any(doc.language == "Japanese" for doc in documents)
    assert any(doc.language == "English" for doc in documents)
    assert all(doc.synthetic for doc in documents)
    assert any(doc.expected_duplicate_group for doc in documents)
    assert any("hard_negative" in doc.evaluation_tags for doc in documents)
    assert any("cross_language" in doc.evaluation_tags for doc in documents)


def test_benchmark_loader_rejects_invalid_records(tmp_path):
    bad_path = tmp_path / "bad.jsonl"
    bad_path.write_text(json.dumps({"benchmark_document_id": "bad"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_benchmark(bad_path)


def test_evaluation_results_are_deterministic():
    documents = load_benchmark(FIXTURE_PATH)

    first = result_to_dict(evaluate_documents(documents))
    second = result_to_dict(evaluate_documents(documents))

    assert first["duplicate_metrics"] == second["duplicate_metrics"]
    assert first["clustering_metrics"] == second["clustering_metrics"]
    assert first["product_metrics"] == second["product_metrics"]
    assert first["predicted_event_by_document"] == second["predicted_event_by_document"]


def test_duplicate_precision_recall_calculation():
    docs = [
        make_doc("a1", "event-a", duplicate_group="dup-a"),
        make_doc("a2", "event-a", duplicate_group="dup-a"),
        make_doc("b1", "event-b"),
    ]
    predicted = {"a1": "p1", "a2": "p1", "b1": "p2"}
    methods = {"a1": "new_event", "a2": "normalized_url", "b1": "new_event"}

    metrics = calculate_duplicate_metrics(docs, predicted, methods)

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["false_positive_count"] == 0
    assert metrics["false_negative_count"] == 0


def test_pairwise_clustering_metrics_count_false_merges_and_splits():
    docs = [
        make_doc("a1", "event-a"),
        make_doc("a2", "event-a"),
        make_doc("b1", "event-b"),
        make_doc("b2", "event-b"),
    ]
    predicted = {"a1": "p1", "a2": "p2", "b1": "p2", "b2": "p3"}

    metrics = calculate_clustering_metrics(docs, predicted)

    assert metrics["pairwise_false_positive_count"] == 1
    assert metrics["pairwise_false_negative_count"] == 2
    assert metrics["pairwise_precision"] == 0.0
    assert metrics["pairwise_recall"] == 0.0


def test_false_merge_detection_and_category():
    documents = load_benchmark(FIXTURE_PATH)
    result = evaluate_documents(documents)

    false_merges = [error for error in result.errors if error.predicted_same_event and not error.gold_same_event]

    assert result.product_metrics["false_merge_count"] >= 1
    assert any(error.error_category == "false title match" for error in false_merges)
    assert any("dev-cloud-procurement-1" in {error.left_id, error.right_id} for error in false_merges)


def test_false_split_detection_and_cross_language_category():
    documents = load_benchmark(FIXTURE_PATH)
    result = evaluate_documents(documents)

    false_splits = [error for error in result.errors if error.gold_same_event and not error.predicted_same_event]

    assert result.product_metrics["false_split_count"] > 0
    assert any(error.error_category == "cross-language false split" for error in false_splits)


def test_japanese_and_english_reporting_metrics_are_explicit():
    documents = load_benchmark(FIXTURE_PATH)
    result = evaluate_documents(documents)

    assert result.product_metrics["cross_language_pair_count"] > 0
    assert result.product_metrics["japanese_title_pair_count"] > 0
    assert "cross_language_match_accuracy" in result.product_metrics
    assert "japanese_title_match_accuracy" in result.product_metrics


def test_recurring_title_and_hard_negative_separation_are_reported():
    documents = load_benchmark(FIXTURE_PATH)
    result = evaluate_documents(documents)

    assert result.product_metrics["recurring_title_pair_count"] > 0
    assert result.product_metrics["hard_negative_pair_count"] > 0
    assert result.product_metrics["hard_negative_accuracy"] < 1.0


def test_metadata_quality_flags_missing_and_malformed_fields():
    documents = load_benchmark(FIXTURE_PATH)
    metadata = calculate_metadata_quality(documents)

    assert metadata["flagged_document_count"] >= 3
    assert metadata["flag_counts"]["missing title"] == 1
    assert metadata["flag_counts"]["URL-path-like title"] == 1
    assert metadata["flag_counts"]["unsupported or missing language"] == 1
    assert metadata["flag_counts"]["missing publisher when source exists"] == 1


def test_threshold_sweep_uses_development_and_reports_held_out_test():
    documents = load_benchmark(FIXTURE_PATH)

    sweep = sweep_thresholds(
        documents,
        title_thresholds=(0.85, 0.92),
        semantic_thresholds=(0.65, 0.78),
        window_days_values=(7, 14),
    )

    assert len(sweep["development_rows"]) == 8
    assert sweep["best_development_config"]["pairwise_f1"] >= 0
    assert sweep["held_out_test_result"]["split"] == "test"
    assert sweep["held_out_test_result"]["benchmark_size"] == len(split_documents(documents, "test"))


def test_development_and_test_split_separation():
    documents = load_benchmark(FIXTURE_PATH)

    development = split_documents(documents, "development")
    test = split_documents(documents, "test")

    assert development
    assert test
    assert not ({doc.benchmark_document_id for doc in development} & {doc.benchmark_document_id for doc in test})
    assert all(doc.split == "development" for doc in development)
    assert all(doc.split == "test" for doc in test)


def test_evaluation_does_not_use_production_database():
    documents = load_benchmark(FIXTURE_PATH)[:3]

    result = evaluate_documents(documents)

    assert result.production_database_url_used == "not used; isolated sqlite:///:memory:"
    assert evaluator.settings.database_url not in result.production_database_url_used


def test_json_and_markdown_reports_are_stable():
    documents = load_benchmark(FIXTURE_PATH)
    result = evaluate_documents(documents)

    payload = result_to_dict(result)
    summary = render_markdown_summary(result)
    errors = render_markdown_errors(result)

    assert payload["benchmark_size"] == len(documents)
    assert "# Phase 11A Event Clustering Baseline" in summary
    assert "## Duplicate Detection" in summary
    assert "# Phase 11A Event Clustering Error Analysis" in errors
    assert "| documents | gold labels | predicted labels |" in errors


def test_evaluator_reuses_current_production_assignment_helper(monkeypatch):
    documents = load_benchmark(FIXTURE_PATH)[:4]
    calls = {"count": 0}

    def counting_assign_document_to_event(db, *, document_id: int):
        calls["count"] += 1
        return production_assign_document_to_event(db, document_id=document_id)

    monkeypatch.setattr(evaluator, "assign_document_to_event", counting_assign_document_to_event)

    evaluate_documents(documents)

    assert calls["count"] == len(documents)


def test_error_categorization_for_duplicate_false_split():
    left = make_doc("a1", "event-a", duplicate_group="dup-a")
    right = replace(make_doc("a2", "event-a", duplicate_group="dup-a"), summary=left.summary)
    predicted = {"a1": "p1", "a2": "p2"}
    methods = {"a1": "new_event", "a2": "new_event"}
    scores = {"a1": 1.0, "a2": 1.0}

    errors = categorize_errors(
        [left, right],
        predicted,
        methods,
        scores,
        ThresholdConfig(title_threshold=0.92, semantic_threshold=0.78, window_days=14),
    )

    assert len(errors) == 1
    assert errors[0].error_category == "duplicate-content failure"


def test_product_metrics_hard_negative_accuracy():
    docs = [
        make_doc("a1", "event-a", tags=("hard_negative",)),
        make_doc("b1", "event-b", tags=("hard_negative",)),
    ]
    predicted_separate = {"a1": "p1", "b1": "p2"}
    predicted_merged = {"a1": "p1", "b1": "p1"}

    assert calculate_product_metrics(docs, predicted_separate)["hard_negative_accuracy"] == 1.0
    assert calculate_product_metrics(docs, predicted_merged)["hard_negative_accuracy"] == 0.0
