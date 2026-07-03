from __future__ import annotations

import argparse
import json
import math
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from itertools import combinations, product
from pathlib import Path
from typing import Iterable

from sklearn.metrics import adjusted_rand_score
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.document import Document
from app.models.event import Event, EventDocument
from app.models.source import Source
from app.services.events import (
    assign_document_to_event,
    content_hash,
    normalize_title,
    normalize_url,
    semantic_text_similarity,
    title_similarity,
)

VALID_SPLITS = {"development", "test"}
DUPLICATE_METHODS = {"exact_canonical_url", "normalized_url", "content_hash"}
FIXED_FETCHED_AT = datetime(2026, 7, 3, 0, 0, 0)
SUPPORTED_LANGUAGES = {"English", "Japanese"}


@dataclass(frozen=True)
class BenchmarkDocument:
    benchmark_document_id: str
    event_label: str
    language: str
    title: str
    summary: str
    canonical_url: str
    source_name: str
    publisher: str
    published_date: date | None
    expected_duplicate_group: str
    notes: str
    split: str
    evaluation_tags: tuple[str, ...] = field(default_factory=tuple)
    synthetic: bool = True


@dataclass(frozen=True)
class ThresholdConfig:
    title_threshold: float
    semantic_threshold: float
    window_days: int


@dataclass
class PairDiagnostic:
    left_id: str
    right_id: str
    gold_same_event: bool
    predicted_same_event: bool
    gold_event_left: str
    gold_event_right: str
    predicted_event_left: str
    predicted_event_right: str
    similarity_score: float | None
    clustering_method: str
    relevant_threshold: float | int | None
    error_category: str
    explanation: str


@dataclass
class EvaluationResult:
    split: str
    threshold_config: ThresholdConfig
    documents: list[BenchmarkDocument]
    predicted_event_by_document: dict[str, str]
    clustering_method_by_document: dict[str, str]
    similarity_by_document: dict[str, float | None]
    duplicate_metrics: dict
    clustering_metrics: dict
    product_metrics: dict
    metadata_quality: dict
    errors: list[PairDiagnostic]
    production_database_url_used: str


def load_benchmark(path: str | Path) -> list[BenchmarkDocument]:
    documents: list[BenchmarkDocument] = []
    seen_ids: set[str] = set()
    required_fields = {
        "benchmark_document_id",
        "event_label",
        "language",
        "title",
        "summary",
        "canonical_url",
        "source_name",
        "publisher",
        "published_date",
        "expected_duplicate_group",
        "notes",
        "split",
    }

    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc

        missing = sorted(required_fields - set(payload))
        if missing:
            raise ValueError(f"Line {line_number} is missing required fields: {', '.join(missing)}")

        document_id = str(payload["benchmark_document_id"]).strip()
        if not document_id:
            raise ValueError(f"Line {line_number} has an empty benchmark_document_id")
        if document_id in seen_ids:
            raise ValueError(f"Duplicate benchmark_document_id: {document_id}")
        seen_ids.add(document_id)

        split = str(payload["split"]).strip()
        if split not in VALID_SPLITS:
            raise ValueError(f"{document_id} has invalid split {split!r}")

        published_date = _parse_optional_date(payload.get("published_date"), document_id)
        tags = payload.get("evaluation_tags") or []
        if not isinstance(tags, list):
            raise ValueError(f"{document_id} evaluation_tags must be a list")

        documents.append(
            BenchmarkDocument(
                benchmark_document_id=document_id,
                event_label=str(payload["event_label"]).strip(),
                language=str(payload["language"]).strip(),
                title=str(payload["title"]),
                summary=str(payload["summary"]),
                canonical_url=str(payload["canonical_url"]).strip(),
                source_name=str(payload["source_name"]).strip(),
                publisher=str(payload["publisher"]).strip(),
                published_date=published_date,
                expected_duplicate_group=str(payload["expected_duplicate_group"]).strip(),
                notes=str(payload["notes"]).strip(),
                split=split,
                evaluation_tags=tuple(str(tag).strip() for tag in tags if str(tag).strip()),
                synthetic=bool(payload.get("synthetic", True)),
            )
        )

    if not documents:
        raise ValueError("Benchmark dataset is empty")
    if {doc.split for doc in documents} != VALID_SPLITS:
        raise ValueError("Benchmark dataset must include development and test splits")
    return documents


def _parse_optional_date(value, document_id: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{document_id} has invalid published_date {value!r}") from exc


def current_threshold_config() -> ThresholdConfig:
    return ThresholdConfig(
        title_threshold=settings.event_near_duplicate_title_threshold,
        semantic_threshold=settings.event_semantic_similarity_threshold,
        window_days=settings.event_title_match_window_days,
    )


@contextmanager
def temporary_thresholds(config: ThresholdConfig):
    original = current_threshold_config()
    settings.event_near_duplicate_title_threshold = config.title_threshold
    settings.event_semantic_similarity_threshold = config.semantic_threshold
    settings.event_title_match_window_days = config.window_days
    try:
        yield
    finally:
        settings.event_near_duplicate_title_threshold = original.title_threshold
        settings.event_semantic_similarity_threshold = original.semantic_threshold
        settings.event_title_match_window_days = original.window_days


def evaluate_documents(
    documents: list[BenchmarkDocument],
    *,
    split_name: str = "all",
    threshold_config: ThresholdConfig | None = None,
) -> EvaluationResult:
    config = threshold_config or current_threshold_config()
    with temporary_thresholds(config):
        session = _build_evaluation_session()
        try:
            source_ids = _insert_sources(session, documents)
            predicted_event_by_document: dict[str, str] = {}
            clustering_method_by_document: dict[str, str] = {}
            similarity_by_document: dict[str, float | None] = {}

            for index, fixture in enumerate(documents, start=1):
                document = Document(
                    id=index,
                    source_id=source_ids.get(fixture.source_name),
                    title=fixture.title,
                    url=fixture.canonical_url,
                    published_date=fixture.published_date,
                    fetched_at=_fetched_at_for(fixture),
                    language=fixture.language or None,
                    raw_text=fixture.summary,
                    cleaned_text=fixture.summary,
                    summary=fixture.summary,
                    topic_tags="; ".join(fixture.evaluation_tags),
                    sensitivity_level="medium",
                    status="ingested",
                )
                session.add(document)
                session.commit()

                link = assign_document_to_event(session, document_id=document.id)
                predicted_event_by_document[fixture.benchmark_document_id] = f"predicted-event-{link.event_id}"
                clustering_method_by_document[fixture.benchmark_document_id] = link.clustering_method
                similarity_by_document[fixture.benchmark_document_id] = link.similarity_score

            result = _build_result(
                split_name=split_name,
                threshold_config=config,
                documents=documents,
                predicted_event_by_document=predicted_event_by_document,
                clustering_method_by_document=clustering_method_by_document,
                similarity_by_document=similarity_by_document,
            )
        finally:
            session.close()
        return result


def _build_evaluation_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Source.__table__.create(bind=engine)
    Document.__table__.create(bind=engine)
    Event.__table__.create(bind=engine)
    EventDocument.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _insert_sources(session: Session, documents: list[BenchmarkDocument]) -> dict[str, int]:
    source_ids: dict[str, int] = {}
    for fixture in documents:
        if not fixture.source_name or fixture.source_name in source_ids:
            continue
        source = Source(
            name=fixture.source_name,
            base_url=_base_url(fixture.canonical_url),
            source_type="benchmark",
            reliability_tier="benchmark",
            country_or_institution=fixture.publisher or None,
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        source_ids[fixture.source_name] = source.id
    return source_ids


def _base_url(url: str) -> str | None:
    normalized = normalize_url(url)
    match = re.match(r"^(https?://[^/]+)", normalized)
    return match.group(1) if match else None


def _fetched_at_for(fixture: BenchmarkDocument) -> datetime:
    if "metadata_quality" in fixture.evaluation_tags:
        return FIXED_FETCHED_AT
    if fixture.published_date:
        return datetime.combine(fixture.published_date, time(hour=12))
    return FIXED_FETCHED_AT


def _build_result(
    *,
    split_name: str,
    threshold_config: ThresholdConfig,
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
    clustering_method_by_document: dict[str, str],
    similarity_by_document: dict[str, float | None],
) -> EvaluationResult:
    duplicate_metrics = calculate_duplicate_metrics(
        documents,
        predicted_event_by_document,
        clustering_method_by_document,
    )
    clustering_metrics = calculate_clustering_metrics(documents, predicted_event_by_document)
    product_metrics = calculate_product_metrics(documents, predicted_event_by_document)
    metadata_quality = calculate_metadata_quality(documents)
    errors = categorize_errors(
        documents,
        predicted_event_by_document,
        clustering_method_by_document,
        similarity_by_document,
        threshold_config,
    )
    return EvaluationResult(
        split=split_name,
        threshold_config=threshold_config,
        documents=documents,
        predicted_event_by_document=predicted_event_by_document,
        clustering_method_by_document=clustering_method_by_document,
        similarity_by_document=similarity_by_document,
        duplicate_metrics=duplicate_metrics,
        clustering_metrics=clustering_metrics,
        product_metrics=product_metrics,
        metadata_quality=metadata_quality,
        errors=errors,
        production_database_url_used="not used; isolated sqlite:///:memory:",
    )


def calculate_duplicate_metrics(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
    clustering_method_by_document: dict[str, str],
) -> dict:
    gold_pairs = {
        _pair_id(left, right)
        for left, right in combinations(documents, 2)
        if left.expected_duplicate_group
        and left.expected_duplicate_group == right.expected_duplicate_group
    }
    predicted_pairs = {
        _pair_id(left, right)
        for left, right in combinations(documents, 2)
        if predicted_event_by_document[left.benchmark_document_id]
        == predicted_event_by_document[right.benchmark_document_id]
        and (
            clustering_method_by_document[left.benchmark_document_id] in DUPLICATE_METHODS
            or clustering_method_by_document[right.benchmark_document_id] in DUPLICATE_METHODS
        )
    }
    return _precision_recall_counts(gold_pairs, predicted_pairs)


def calculate_clustering_metrics(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
) -> dict:
    gold_pairs = {
        _pair_id(left, right)
        for left, right in combinations(documents, 2)
        if left.event_label == right.event_label
    }
    predicted_pairs = {
        _pair_id(left, right)
        for left, right in combinations(documents, 2)
        if predicted_event_by_document[left.benchmark_document_id]
        == predicted_event_by_document[right.benchmark_document_id]
    }
    pairwise = _precision_recall_counts(gold_pairs, predicted_pairs)
    bcubed = _bcubed_metrics(documents, predicted_event_by_document)
    adjusted_rand = adjusted_rand_score(
        [doc.event_label for doc in documents],
        [predicted_event_by_document[doc.benchmark_document_id] for doc in documents],
    )
    return {
        "pairwise_precision": pairwise["precision"],
        "pairwise_recall": pairwise["recall"],
        "pairwise_f1": pairwise["f1"],
        "pairwise_false_positive_count": pairwise["false_positive_count"],
        "pairwise_false_negative_count": pairwise["false_negative_count"],
        "pairwise_true_positive_count": pairwise["true_positive_count"],
        "bcubed_precision": bcubed["precision"],
        "bcubed_recall": bcubed["recall"],
        "bcubed_f1": bcubed["f1"],
        "adjusted_rand_index": adjusted_rand,
    }


def calculate_product_metrics(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
) -> dict:
    false_merge_pairs = []
    false_split_pairs = []
    predicted_same_pairs = 0
    gold_same_pairs = 0
    cross_language_total = 0
    cross_language_correct = 0
    japanese_title_total = 0
    japanese_title_correct = 0
    recurring_total = 0
    recurring_correct = 0
    hard_negative_total = 0
    hard_negative_correct = 0

    for left, right in combinations(documents, 2):
        gold_same = left.event_label == right.event_label
        predicted_same = (
            predicted_event_by_document[left.benchmark_document_id]
            == predicted_event_by_document[right.benchmark_document_id]
        )
        if gold_same:
            gold_same_pairs += 1
        if predicted_same:
            predicted_same_pairs += 1
        if predicted_same and not gold_same:
            false_merge_pairs.append(_pair_id(left, right))
        if gold_same and not predicted_same:
            false_split_pairs.append(_pair_id(left, right))

        languages = {left.language, right.language}
        if gold_same and languages == {"English", "Japanese"}:
            cross_language_total += 1
            if predicted_same:
                cross_language_correct += 1
        if gold_same and left.language == "Japanese" and right.language == "Japanese":
            japanese_title_total += 1
            if predicted_same:
                japanese_title_correct += 1

        tags = set(left.evaluation_tags) | set(right.evaluation_tags)
        same_normalized_title = normalize_title(left.title) == normalize_title(right.title)
        if not gold_same and "recurring_title" in tags and same_normalized_title:
            recurring_total += 1
            if not predicted_same:
                recurring_correct += 1
        if not gold_same and "hard_negative" in tags:
            hard_negative_total += 1
            if not predicted_same:
                hard_negative_correct += 1

    perfect_events = _perfect_event_percentage(documents, predicted_event_by_document)
    return {
        "false_merge_rate": _safe_div(len(false_merge_pairs), predicted_same_pairs),
        "false_split_rate": _safe_div(len(false_split_pairs), gold_same_pairs),
        "false_merge_count": len(false_merge_pairs),
        "false_split_count": len(false_split_pairs),
        "perfect_event_percentage": perfect_events,
        "cross_language_match_accuracy": _safe_div(cross_language_correct, cross_language_total),
        "cross_language_pair_count": cross_language_total,
        "japanese_title_match_accuracy": _safe_div(japanese_title_correct, japanese_title_total),
        "japanese_title_pair_count": japanese_title_total,
        "recurring_title_separation_accuracy": _safe_div(recurring_correct, recurring_total),
        "recurring_title_pair_count": recurring_total,
        "hard_negative_accuracy": _safe_div(hard_negative_correct, hard_negative_total),
        "hard_negative_pair_count": hard_negative_total,
    }


def calculate_metadata_quality(documents: list[BenchmarkDocument]) -> dict:
    flags: dict[str, list[str]] = {}
    for fixture in documents:
        document_flags = []
        if not fixture.title.strip():
            document_flags.append("missing title")
        if len(fixture.title) > 500:
            document_flags.append("title longer than configured limit")
        if _is_url_path_like_title(fixture.title):
            document_flags.append("URL-path-like title")
        if not fixture.source_name:
            document_flags.append("missing source")
        if fixture.source_name and not fixture.publisher:
            document_flags.append("missing publisher when source exists")
        if fixture.published_date and fixture.published_date > _fetched_at_for(fixture).date():
            document_flags.append("publication date later than fetched date")
        if fixture.published_date and (fixture.published_date < date(1990, 1, 1) or fixture.published_date > FIXED_FETCHED_AT.date()):
            document_flags.append("implausible publication date")
        if not fixture.language or fixture.language not in SUPPORTED_LANGUAGES:
            document_flags.append("unsupported or missing language")
        if document_flags:
            flags[fixture.benchmark_document_id] = document_flags

    counts: dict[str, int] = {}
    for document_flags in flags.values():
        for item in document_flags:
            counts[item] = counts.get(item, 0) + 1
    return {
        "flagged_document_count": len(flags),
        "flag_counts": dict(sorted(counts.items())),
        "flags_by_document": flags,
    }


def _is_url_path_like_title(title: str) -> bool:
    stripped = title.strip().lower()
    if not stripped:
        return False
    return "/" in stripped and (
        stripped.endswith(".html")
        or stripped.endswith(".htm")
        or stripped.endswith(".pdf")
        or re.search(r"/20\d{2}/", stripped) is not None
    )


def categorize_errors(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
    clustering_method_by_document: dict[str, str],
    similarity_by_document: dict[str, float | None],
    threshold_config: ThresholdConfig,
) -> list[PairDiagnostic]:
    errors = []
    for left, right in combinations(documents, 2):
        gold_same = left.event_label == right.event_label
        predicted_same = (
            predicted_event_by_document[left.benchmark_document_id]
            == predicted_event_by_document[right.benchmark_document_id]
        )
        if gold_same == predicted_same:
            continue

        later = right
        method = clustering_method_by_document.get(later.benchmark_document_id, "not_clustered")
        score = similarity_by_document.get(later.benchmark_document_id)
        threshold = _threshold_for_method(method, threshold_config)
        if gold_same and not predicted_same:
            score, method, threshold = _best_pair_similarity(left, right, threshold_config)
        elif score is None:
            score, method, threshold = _best_pair_similarity(left, right, threshold_config)

        category, explanation = _error_category(
            left,
            right,
            gold_same=gold_same,
            predicted_same=predicted_same,
            method=method,
            threshold_config=threshold_config,
        )
        errors.append(
            PairDiagnostic(
                left_id=left.benchmark_document_id,
                right_id=right.benchmark_document_id,
                gold_same_event=gold_same,
                predicted_same_event=predicted_same,
                gold_event_left=left.event_label,
                gold_event_right=right.event_label,
                predicted_event_left=predicted_event_by_document[left.benchmark_document_id],
                predicted_event_right=predicted_event_by_document[right.benchmark_document_id],
                similarity_score=score,
                clustering_method=method,
                relevant_threshold=threshold,
                error_category=category,
                explanation=explanation,
            )
        )
    return errors


def _error_category(
    left: BenchmarkDocument,
    right: BenchmarkDocument,
    *,
    gold_same: bool,
    predicted_same: bool,
    method: str,
    threshold_config: ThresholdConfig,
) -> tuple[str, str]:
    tags = set(left.evaluation_tags) | set(right.evaluation_tags)
    metadata_flags = calculate_metadata_quality([left, right])["flagged_document_count"] > 0
    date_gap = _date_gap_days(left, right)

    if predicted_same and not gold_same:
        if "recurring_title" in tags and normalize_title(left.title) == normalize_title(right.title):
            return "recurring-title false merge", "Different recurring events with the same normalized title were clustered together."
        if method == "near_duplicate_title":
            return "false title match", "Title similarity passed the near-duplicate threshold for different gold events."
        if method == "semantic_title_summary":
            return "false semantic match", "Character n-gram similarity passed the semantic threshold for different gold events."
        if method == "normalized_url":
            return "URL normalization failure", "URL normalization linked documents with different gold event labels."
        if method == "content_hash":
            return "duplicate-content failure", "Content hash linked documents with different gold event labels."
        return "other", "Predicted event cluster contains different gold event labels."

    if gold_same and not predicted_same:
        languages = {left.language, right.language}
        if languages == {"English", "Japanese"}:
            return "cross-language false split", "English and Japanese documents for the same event were not clustered together."
        if left.expected_duplicate_group and left.expected_duplicate_group == right.expected_duplicate_group:
            if normalize_url(left.canonical_url) == normalize_url(right.canonical_url):
                return "URL normalization failure", "Expected duplicate URL variants were not clustered together."
            if content_hash(left.summary) == content_hash(right.summary):
                return "duplicate-content failure", "Expected identical-content duplicates were not clustered together."
        if date_gap is not None and date_gap > threshold_config.window_days:
            return "date-window failure", "Same-event documents fell outside the configured event title match window."
        if metadata_flags:
            return "missing metadata", "Missing or malformed metadata likely weakened event assignment."
        return "low-confidence new-event creation", "Same-event documents did not pass current title or semantic thresholds."

    return "other", "Unexpected error state."


def _date_gap_days(left: BenchmarkDocument, right: BenchmarkDocument) -> int | None:
    if not left.published_date or not right.published_date:
        return None
    return abs((left.published_date - right.published_date).days)


def _best_pair_similarity(
    left: BenchmarkDocument,
    right: BenchmarkDocument,
    threshold_config: ThresholdConfig,
) -> tuple[float, str, float | int]:
    title_score = title_similarity(left.title, right.title)
    semantic_score = semantic_text_similarity(
        " ".join([left.title, left.summary]),
        " ".join([right.title, right.summary]),
    )
    if title_score >= semantic_score:
        return title_score, "near_duplicate_title", threshold_config.title_threshold
    return semantic_score, "semantic_title_summary", threshold_config.semantic_threshold


def _threshold_for_method(method: str, threshold_config: ThresholdConfig) -> float | int | None:
    if method == "near_duplicate_title":
        return threshold_config.title_threshold
    if method == "semantic_title_summary":
        return threshold_config.semantic_threshold
    if method in DUPLICATE_METHODS or method == "new_event":
        return None
    return threshold_config.window_days


def _precision_recall_counts(gold_pairs: set[tuple[str, str]], predicted_pairs: set[tuple[str, str]]) -> dict:
    true_positive = len(gold_pairs & predicted_pairs)
    false_positive = len(predicted_pairs - gold_pairs)
    false_negative = len(gold_pairs - predicted_pairs)
    precision = _safe_div(true_positive, true_positive + false_positive)
    recall = _safe_div(true_positive, true_positive + false_negative)
    f1 = _f1(precision, recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive_count": true_positive,
        "false_positive_count": false_positive,
        "false_negative_count": false_negative,
        "gold_pair_count": len(gold_pairs),
        "predicted_pair_count": len(predicted_pairs),
    }


def _bcubed_metrics(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
) -> dict:
    precision_values = []
    recall_values = []
    for fixture in documents:
        predicted_cluster = {
            doc.benchmark_document_id
            for doc in documents
            if predicted_event_by_document[doc.benchmark_document_id]
            == predicted_event_by_document[fixture.benchmark_document_id]
        }
        gold_cluster = {
            doc.benchmark_document_id for doc in documents if doc.event_label == fixture.event_label
        }
        overlap = len(predicted_cluster & gold_cluster)
        precision_values.append(_safe_div(overlap, len(predicted_cluster)))
        recall_values.append(_safe_div(overlap, len(gold_cluster)))
    precision = sum(precision_values) / len(precision_values)
    recall = sum(recall_values) / len(recall_values)
    return {"precision": precision, "recall": recall, "f1": _f1(precision, recall)}


def _perfect_event_percentage(
    documents: list[BenchmarkDocument],
    predicted_event_by_document: dict[str, str],
) -> float:
    gold_labels = sorted({doc.event_label for doc in documents})
    perfect = 0
    for label in gold_labels:
        gold_docs = {doc.benchmark_document_id for doc in documents if doc.event_label == label}
        predicted_clusters = {
            frozenset(
                candidate.benchmark_document_id
                for candidate in documents
                if predicted_event_by_document[candidate.benchmark_document_id]
                == predicted_event_by_document[doc_id]
            )
            for doc_id in gold_docs
        }
        if predicted_clusters == {frozenset(gold_docs)}:
            perfect += 1
    return _safe_div(perfect, len(gold_labels))


def _pair_id(left: BenchmarkDocument, right: BenchmarkDocument) -> tuple[str, str]:
    return tuple(sorted((left.benchmark_document_id, right.benchmark_document_id)))


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def split_documents(documents: list[BenchmarkDocument], split: str | None) -> list[BenchmarkDocument]:
    if split in (None, "all"):
        return list(documents)
    if split not in VALID_SPLITS:
        raise ValueError(f"Unknown split {split!r}")
    return [doc for doc in documents if doc.split == split]


def sweep_thresholds(
    documents: list[BenchmarkDocument],
    *,
    title_thresholds: Iterable[float] = (0.85, 0.90, 0.92, 0.95, 0.97),
    semantic_thresholds: Iterable[float] = (0.65, 0.70, 0.78, 0.85, 0.90),
    window_days_values: Iterable[int] = (7, 14, 30, 90),
) -> dict:
    development_documents = split_documents(documents, "development")
    rows = []
    best_row = None
    for title_threshold, semantic_threshold, window_days in product(
        title_thresholds,
        semantic_thresholds,
        window_days_values,
    ):
        config = ThresholdConfig(title_threshold, semantic_threshold, window_days)
        result = evaluate_documents(development_documents, split_name="development", threshold_config=config)
        row = {
            "title_threshold": title_threshold,
            "semantic_threshold": semantic_threshold,
            "window_days": window_days,
            "pairwise_f1": result.clustering_metrics["pairwise_f1"],
            "pairwise_precision": result.clustering_metrics["pairwise_precision"],
            "pairwise_recall": result.clustering_metrics["pairwise_recall"],
            "false_merge_count": result.product_metrics["false_merge_count"],
            "false_split_count": result.product_metrics["false_split_count"],
            "cross_language_match_accuracy": result.product_metrics["cross_language_match_accuracy"],
        }
        rows.append(row)
        if best_row is None or _sweep_sort_key(row) > _sweep_sort_key(best_row):
            best_row = row

    assert best_row is not None
    selected_config = ThresholdConfig(
        best_row["title_threshold"],
        best_row["semantic_threshold"],
        best_row["window_days"],
    )
    test_result = evaluate_documents(
        split_documents(documents, "test"),
        split_name="test",
        threshold_config=selected_config,
    )
    return {
        "development_rows": rows,
        "best_development_config": best_row,
        "held_out_test_result": result_to_dict(test_result),
    }


def _sweep_sort_key(row: dict) -> tuple[float, float, float, float, int]:
    return (
        row["pairwise_f1"],
        -row["false_merge_count"],
        row["pairwise_precision"],
        row["pairwise_recall"],
        -row["window_days"],
    )


def result_to_dict(result: EvaluationResult) -> dict:
    return {
        "split": result.split,
        "threshold_config": asdict(result.threshold_config),
        "benchmark_size": len(result.documents),
        "event_group_count": len({doc.event_label for doc in result.documents}),
        "language_counts": _count_by(result.documents, lambda doc: doc.language or "missing"),
        "duplicate_metrics": _round_floats(result.duplicate_metrics),
        "clustering_metrics": _round_floats(result.clustering_metrics),
        "product_metrics": _round_floats(result.product_metrics),
        "metadata_quality": result.metadata_quality,
        "predicted_event_by_document": result.predicted_event_by_document,
        "clustering_method_by_document": result.clustering_method_by_document,
        "similarity_by_document": _round_floats(result.similarity_by_document),
        "error_count": len(result.errors),
        "errors": [_round_floats(asdict(error)) for error in result.errors],
        "production_database_url_used": result.production_database_url_used,
    }


def _count_by(documents: list[BenchmarkDocument], key_func) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc in documents:
        key = str(key_func(doc))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _round_floats(value):
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_floats(item) for item in value]
    return value


def render_markdown_summary(result: EvaluationResult, *, sweep: dict | None = None) -> str:
    data = result_to_dict(result)
    lines = [
        "# Phase 11A Event Clustering Baseline",
        "",
        f"- Split: `{data['split']}`",
        f"- Benchmark documents: `{data['benchmark_size']}`",
        f"- Gold event groups: `{data['event_group_count']}`",
        f"- Languages: `{json.dumps(data['language_counts'], ensure_ascii=False)}`",
        f"- Thresholds: title `{result.threshold_config.title_threshold}`, semantic `{result.threshold_config.semantic_threshold}`, window `{result.threshold_config.window_days}` days",
        f"- Production database: {result.production_database_url_used}",
        "",
        "## Duplicate Detection",
        "",
        _metric_line(data["duplicate_metrics"], "precision", "recall", "f1"),
        f"- False positives: `{data['duplicate_metrics']['false_positive_count']}`",
        f"- False negatives: `{data['duplicate_metrics']['false_negative_count']}`",
        "",
        "## Event Clustering",
        "",
        _metric_line(data["clustering_metrics"], "pairwise_precision", "pairwise_recall", "pairwise_f1"),
        f"- B-cubed F1: `{data['clustering_metrics']['bcubed_f1']}`",
        f"- Adjusted Rand Index: `{data['clustering_metrics']['adjusted_rand_index']}`",
        f"- Pairwise false positives: `{data['clustering_metrics']['pairwise_false_positive_count']}`",
        f"- Pairwise false negatives: `{data['clustering_metrics']['pairwise_false_negative_count']}`",
        "",
        "## Product Metrics",
        "",
        f"- False merge rate: `{data['product_metrics']['false_merge_rate']}`",
        f"- False split rate: `{data['product_metrics']['false_split_rate']}`",
        f"- Perfect event percentage: `{data['product_metrics']['perfect_event_percentage']}`",
        f"- Cross-language match accuracy: `{data['product_metrics']['cross_language_match_accuracy']}` over `{data['product_metrics']['cross_language_pair_count']}` pairs",
        f"- Japanese-title match accuracy: `{data['product_metrics']['japanese_title_match_accuracy']}` over `{data['product_metrics']['japanese_title_pair_count']}` pairs",
        f"- Recurring-title separation accuracy: `{data['product_metrics']['recurring_title_separation_accuracy']}` over `{data['product_metrics']['recurring_title_pair_count']}` pairs",
        f"- Hard-negative accuracy: `{data['product_metrics']['hard_negative_accuracy']}` over `{data['product_metrics']['hard_negative_pair_count']}` pairs",
        "",
        "## Metadata Quality",
        "",
        f"- Flagged documents: `{data['metadata_quality']['flagged_document_count']}`",
        f"- Flag counts: `{json.dumps(data['metadata_quality']['flag_counts'], ensure_ascii=False)}`",
    ]
    if sweep:
        best = sweep["best_development_config"]
        held = sweep["held_out_test_result"]
        lines.extend(
            [
                "",
                "## Threshold Sweep",
                "",
                f"- Best development config: title `{best['title_threshold']}`, semantic `{best['semantic_threshold']}`, window `{best['window_days']}` days",
                f"- Best development pairwise F1: `{round(best['pairwise_f1'], 6)}`",
                f"- Held-out test pairwise F1: `{held['clustering_metrics']['pairwise_f1']}`",
                f"- Held-out test false merges: `{held['product_metrics']['false_merge_count']}`",
                f"- Held-out test false splits: `{held['product_metrics']['false_split_count']}`",
                "",
                "Top threshold rows by development F1:",
                "",
                "| title | semantic | window_days | pairwise_f1 | precision | recall | false_merges | false_splits |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(sweep["development_rows"], key=_sweep_sort_key, reverse=True)[:10]:
            lines.append(
                f"| {row['title_threshold']} | {row['semantic_threshold']} | {row['window_days']} | "
                f"{round(row['pairwise_f1'], 6)} | {round(row['pairwise_precision'], 6)} | "
                f"{round(row['pairwise_recall'], 6)} | {row['false_merge_count']} | {row['false_split_count']} |"
            )
    lines.append("")
    return "\n".join(lines)


def render_markdown_errors(result: EvaluationResult) -> str:
    lines = [
        "# Phase 11A Event Clustering Error Analysis",
        "",
        f"- Split: `{result.split}`",
        f"- Error pairs: `{len(result.errors)}`",
        "",
        "| documents | gold labels | predicted labels | score | method | threshold | category | explanation |",
        "|---|---|---|---:|---|---:|---|---|",
    ]
    for error in result.errors:
        score = "" if error.similarity_score is None else str(round(error.similarity_score, 6))
        threshold = "" if error.relevant_threshold is None else str(error.relevant_threshold)
        lines.append(
            f"| `{error.left_id}` / `{error.right_id}` | "
            f"`{error.gold_event_left}` / `{error.gold_event_right}` | "
            f"`{error.predicted_event_left}` / `{error.predicted_event_right}` | "
            f"{score} | `{error.clustering_method}` | {threshold} | "
            f"{error.error_category} | {error.explanation} |"
        )
    lines.append("")
    return "\n".join(lines)


def _metric_line(metrics: dict, precision_key: str, recall_key: str, f1_key: str) -> str:
    return (
        f"- Precision: `{metrics[precision_key]}`; "
        f"recall: `{metrics[recall_key]}`; "
        f"F1: `{metrics[f1_key]}`"
    )


def print_terminal_report(result: EvaluationResult, *, sweep: dict | None = None) -> None:
    data = result_to_dict(result)
    print("Phase 11A event clustering evaluation")
    print(f"split={data['split']} documents={data['benchmark_size']} events={data['event_group_count']}")
    print(
        "baseline thresholds "
        f"title={result.threshold_config.title_threshold} "
        f"semantic={result.threshold_config.semantic_threshold} "
        f"window_days={result.threshold_config.window_days}"
    )
    print(
        "duplicate "
        f"precision={data['duplicate_metrics']['precision']} "
        f"recall={data['duplicate_metrics']['recall']} "
        f"f1={data['duplicate_metrics']['f1']} "
        f"fp={data['duplicate_metrics']['false_positive_count']} "
        f"fn={data['duplicate_metrics']['false_negative_count']}"
    )
    print(
        "clustering "
        f"pairwise_precision={data['clustering_metrics']['pairwise_precision']} "
        f"pairwise_recall={data['clustering_metrics']['pairwise_recall']} "
        f"pairwise_f1={data['clustering_metrics']['pairwise_f1']} "
        f"false_merges={data['product_metrics']['false_merge_count']} "
        f"false_splits={data['product_metrics']['false_split_count']}"
    )
    print(
        "language "
        f"cross_language_accuracy={data['product_metrics']['cross_language_match_accuracy']} "
        f"japanese_title_accuracy={data['product_metrics']['japanese_title_match_accuracy']}"
    )
    print(f"metadata_flagged_documents={data['metadata_quality']['flagged_document_count']}")
    print(f"production_database_url_used={result.production_database_url_used}")
    if sweep:
        best = sweep["best_development_config"]
        held = sweep["held_out_test_result"]
        print(
            "sweep best_development "
            f"title={best['title_threshold']} semantic={best['semantic_threshold']} "
            f"window_days={best['window_days']} pairwise_f1={round(best['pairwise_f1'], 6)}"
        )
        print(
            "held_out_test "
            f"pairwise_f1={held['clustering_metrics']['pairwise_f1']} "
            f"false_merges={held['product_metrics']['false_merge_count']} "
            f"false_splits={held['product_metrics']['false_split_count']}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate event clustering against a repository benchmark.")
    parser.add_argument("--dataset", required=True, help="Path to JSONL benchmark dataset.")
    parser.add_argument("--split", choices=["all", "development", "test"], default="all")
    parser.add_argument("--json-report", help="Optional path for machine-readable JSON report.")
    parser.add_argument("--markdown-report", help="Optional path for Markdown summary report.")
    parser.add_argument("--error-report", help="Optional path for Markdown error analysis report.")
    parser.add_argument("--sweep", action="store_true", help="Run development threshold sweep and held-out test evaluation.")
    args = parser.parse_args(argv)

    documents = load_benchmark(args.dataset)
    selected_documents = split_documents(documents, args.split)
    result = evaluate_documents(selected_documents, split_name=args.split)
    sweep = sweep_thresholds(documents) if args.sweep else None

    if args.json_report:
        payload = result_to_dict(result)
        if sweep:
            payload["threshold_sweep"] = _round_floats(sweep)
        _write_text(args.json_report, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if args.markdown_report:
        _write_text(args.markdown_report, render_markdown_summary(result, sweep=sweep))
    if args.error_report:
        _write_text(args.error_report, render_markdown_errors(result))

    print_terminal_report(result, sweep=sweep)
    return 0


def _write_text(path: str | Path, text: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
