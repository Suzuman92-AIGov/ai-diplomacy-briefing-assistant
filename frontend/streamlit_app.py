import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv("../.env")
DEFAULT_API_BASE_URL = "http://localhost:8002"
API_BASE_URL = os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")

st.set_page_config(page_title="AI Diplomacy Briefing Assistant", page_icon="🛰️", layout="wide")
st.title("AI Diplomacy Briefing Assistant")
st.caption("RAG-based policy briefing assistant for AI governance and foreign policy monitoring.")

page = st.sidebar.radio("Go to", ["Start Here",
        "Dashboard",
        "Events",
        "System Status", "Sources",
        "Source Pack", "Ingest URL", "Documents", "Semantic Search",
        "Ask Knowledge Base",
        "Generate Brief",
        "Review Briefs",
        "Export Brief", "Briefs", "Audit Logs", "Governance"])

class FrontendAPIError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_sensitive_error_detail(message: str) -> bool:
    lowered = message.lower()
    sensitive_markers = [
        "traceback",
        "sqlalchemy",
        "psycopg",
        "postgres",
        "select ",
        "insert ",
        "update ",
        "delete ",
        " from ",
        "null value",
        "constraint",
    ]
    return any(marker in lowered for marker in sensitive_markers)


def _concise_error(message: str, fallback: str = "Request failed.") -> str:
    text = " ".join(_safe_text(message).split())
    if not text:
        return fallback
    if _is_sensitive_error_detail(text):
        return fallback
    return text[:220]


def _extract_response_detail(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message")
        if isinstance(detail, (str, int, float)):
            return str(detail)
    return ""


def _request_json(method: str, path: str, *, params: dict | None = None, payload: dict | None = None, timeout: int):
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}{path}",
            params=params,
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise FrontendAPIError("Request timed out. Confirm that the backend is running and try again.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise FrontendAPIError("Backend is not reachable. Confirm that the backend is running.") from exc
    except requests.exceptions.RequestException as exc:
        raise FrontendAPIError(_concise_error(str(exc), "Could not contact the backend.")) from exc

    if response.status_code >= 400:
        detail = _extract_response_detail(response)
        if response.status_code == 404 and detail:
            raise FrontendAPIError(_concise_error(detail, "Requested record was not found."))
        raise FrontendAPIError(_concise_error(detail, f"Backend request failed with status {response.status_code}."))

    try:
        return response.json()
    except ValueError as exc:
        raise FrontendAPIError("Backend returned malformed JSON.") from exc


def api_get(path: str, params: dict | None = None, timeout: int = 20):
    return _request_json("GET", path, params=params, timeout=timeout)


def api_post(path: str, payload: dict | None = None, timeout: int = 180):
    return _request_json("POST", path, payload=payload, timeout=timeout)


def api_patch(path: str, payload: dict | None = None, timeout: int = 60):
    return _request_json("PATCH", path, payload=payload, timeout=timeout)


NO_SOURCE_SELECTED_LABEL = "No source selected"


def normalize_source_name(name: str) -> str:
    return " ".join(name.split())


def find_source_by_name(sources: list[dict], name: str) -> dict | None:
    normalized_name = normalize_source_name(name).lower()
    for source in sources:
        if normalize_source_name(source.get("name", "")).lower() == normalized_name:
            return source
    return None


def build_source_create_payload(
    *,
    name: str,
    base_url: str,
    source_type: str,
    reliability_tier: str,
    country_or_institution: str,
    notes: str,
    is_active: bool,
) -> dict:
    return {
        "name": normalize_source_name(name),
        "base_url": base_url.strip() or None,
        "source_type": source_type,
        "reliability_tier": reliability_tier,
        "country_or_institution": country_or_institution.strip() or None,
        "notes": notes.strip() or None,
        "is_active": is_active,
    }


def build_url_ingest_payload(
    *,
    url: str,
    source_id: int | None,
    topic_tags: str,
    sensitivity_level: str,
    language: str,
) -> dict:
    payload = {
        "url": url,
        "topic_tags": topic_tags,
        "sensitivity_level": sensitivity_level,
        "language": language,
    }
    if source_id is not None and source_id > 0:
        payload["source_id"] = source_id
    return payload


def _parse_datetime(value):
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_date_or_datetime(value):
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    try:
        from datetime import datetime

        return datetime.fromisoformat(f"{value}T00:00:00")
    except (TypeError, ValueError):
        return None


def format_missing(value: str = "Not available") -> str:
    return value


def format_date_value(value) -> str:
    parsed = _parse_date_or_datetime(value)
    if parsed is None:
        return format_missing()
    return parsed.strftime("%b %-d, %Y")


def format_datetime_value(value) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return format_missing()
    return parsed.strftime("%b %-d, %Y %H:%M")


def format_count(value, singular: str, plural: str | None = None) -> str:
    try:
        count = int(value or 0)
    except (TypeError, ValueError):
        count = 0
    label = singular if count == 1 else (plural or f"{singular}s")
    return f"{count:,} {label}"


def format_similarity_score(value) -> str:
    if value is None or value == "":
        return format_missing()
    try:
        score = float(value)
    except (TypeError, ValueError):
        return format_missing()
    percent = score * 100 if score <= 1 else score
    rounded = round(percent, 1)
    if rounded.is_integer():
        return f"{int(rounded)}%"
    return f"{rounded:.1f}%"


def readable_value(value) -> str:
    text = _safe_text(value)
    return text if text else format_missing()


def clustering_method_label(value) -> str:
    method = _safe_text(value)
    labels = {
        "new_event": "Created as a new event",
        "canonical_url": "Matched by canonical URL",
        "exact_canonical_url": "Matched by canonical URL",
        "normalized_url": "Matched by normalized URL",
        "content_hash": "Matched by identical content",
        "near_title": "Matched by similar title",
        "near_duplicate_title": "Matched by similar title",
        "title_similarity": "Matched by similar title",
        "semantic_similarity": "Matched by content similarity",
        "semantic_title_summary": "Matched by content similarity",
    }
    if method in labels:
        return labels[method]
    if not method:
        return format_missing()
    return f"Unknown method ({method.replace('_', ' ')})"


def relationship_type_label(value) -> str:
    relationship = _safe_text(value)
    labels = {
        "primary": "Primary event evidence",
        "secondary": "Related evidence",
    }
    if relationship in labels:
        return labels[relationship]
    if not relationship:
        return format_missing()
    return relationship.replace("_", " ").title()


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_event_payload(item: dict) -> dict:
    if not isinstance(item, dict):
        raise FrontendAPIError("Event data is malformed.")
    event_id = _to_int(item.get("id"), default=-1)
    if event_id < 0:
        raise FrontendAPIError("Event data is incomplete.")

    event = dict(item)
    event["id"] = event_id
    event["title"] = _safe_text(item.get("title")) or f"Event {event_id}"
    event["summary"] = _safe_text(item.get("summary"))
    event["event_type"] = _safe_text(item.get("event_type"))
    event["status"] = _safe_text(item.get("status"))
    event["primary_language"] = _safe_text(item.get("primary_language"))
    event["country_or_region"] = _safe_text(item.get("country_or_region"))
    event["related_document_count"] = _to_int(item.get("related_document_count"), 0)
    event["distinct_source_count"] = _to_int(item.get("distinct_source_count"), 0)
    event["distinct_publisher_count"] = _to_int(item.get("distinct_publisher_count"), event["distinct_source_count"])
    return event


def parse_event_list_response(payload) -> list[dict]:
    if not isinstance(payload, list):
        raise FrontendAPIError("Event list response was malformed.")
    return [normalize_event_payload(item) for item in payload]


def parse_event_detail_response(payload) -> dict:
    if not isinstance(payload, dict):
        raise FrontendAPIError("Event detail response was malformed.")
    event = normalize_event_payload(payload)
    related_documents = payload.get("related_documents", [])
    if related_documents is None:
        related_documents = []
    if not isinstance(related_documents, list):
        raise FrontendAPIError("Event detail documents were malformed.")
    event["related_documents"] = parse_event_documents_response(related_documents)
    return event


def normalize_event_document_payload(item: dict) -> dict:
    if not isinstance(item, dict):
        raise FrontendAPIError("Event document data is malformed.")
    document_id = _to_int(item.get("document_id"), default=-1)
    if document_id < 0:
        raise FrontendAPIError("Event document data is incomplete.")
    document = dict(item)
    document["document_id"] = document_id
    document["event_id"] = _to_int(item.get("event_id"), 0)
    document["document_title"] = _safe_text(item.get("document_title")) or f"Document {document_id}"
    document["source_name"] = _safe_text(item.get("source_name"))
    document["publisher"] = _safe_text(item.get("publisher"))
    document["url"] = _safe_text(item.get("url"))
    document["relationship_type"] = _safe_text(item.get("relationship_type"))
    document["clustering_method"] = _safe_text(item.get("clustering_method"))
    return document


def parse_event_documents_response(payload) -> list[dict]:
    if not isinstance(payload, list):
        raise FrontendAPIError("Event documents response was malformed.")
    return [normalize_event_document_payload(item) for item in payload]


def normalize_event_snapshot_payload(item: dict) -> dict:
    if not isinstance(item, dict):
        raise FrontendAPIError("Event snapshot data is malformed.")
    snapshot_id = _to_int(item.get("id"), default=-1)
    if snapshot_id < 0:
        raise FrontendAPIError("Event snapshot data is incomplete.")
    snapshot = dict(item)
    snapshot["id"] = snapshot_id
    snapshot["event_id"] = _to_int(item.get("event_id"), 0)
    snapshot["snapshot_type"] = _safe_text(item.get("snapshot_type"))
    snapshot["event_title"] = _safe_text(item.get("event_title"))
    snapshot["document_count"] = _to_int(item.get("document_count"), 0)
    snapshot["distinct_source_count"] = _to_int(item.get("distinct_source_count"), 0)
    snapshot["distinct_publisher_count"] = _to_int(item.get("distinct_publisher_count"), 0)
    snapshot["document_ids"] = item.get("document_ids") if isinstance(item.get("document_ids"), list) else []
    snapshot["source_names"] = item.get("source_names") if isinstance(item.get("source_names"), list) else []
    snapshot["publisher_names"] = item.get("publisher_names") if isinstance(item.get("publisher_names"), list) else []
    snapshot["evidence_items"] = item.get("evidence_items") if isinstance(item.get("evidence_items"), list) else []
    snapshot["snapshot_hash"] = _safe_text(item.get("snapshot_hash"))
    return snapshot


def parse_event_snapshot_response(payload) -> dict:
    return normalize_event_snapshot_payload(payload)


def parse_event_snapshots_response(payload) -> list[dict]:
    if not isinstance(payload, list):
        raise FrontendAPIError("Event snapshots response was malformed.")
    return [normalize_event_snapshot_payload(item) for item in payload]


def normalize_event_change_payload(item: dict) -> dict:
    if not isinstance(item, dict):
        raise FrontendAPIError("Event change data is malformed.")
    change = dict(item)
    change["has_changes"] = bool(item.get("has_changes"))
    change["change_level"] = _safe_text(item.get("change_level")) or "none"
    change["is_initial_baseline"] = bool(item.get("is_initial_baseline"))
    for field in [
        "new_document_ids",
        "removed_document_ids",
        "new_sources",
        "removed_sources",
        "new_publishers",
        "removed_publishers",
    ]:
        change[field] = item.get(field) if isinstance(item.get(field), list) else []
    change["document_count_delta"] = _to_int(item.get("document_count_delta"), 0)
    change["source_count_delta"] = _to_int(item.get("source_count_delta"), 0)
    change["publisher_count_delta"] = _to_int(item.get("publisher_count_delta"), 0)
    change["metadata_changes"] = item.get("metadata_changes") if isinstance(item.get("metadata_changes"), dict) else {}
    change["deterministic_change_summary"] = _safe_text(item.get("deterministic_change_summary"))
    return change


def normalize_event_brief_payload(item: dict) -> dict:
    if not isinstance(item, dict):
        raise FrontendAPIError("Event brief data is malformed.")
    brief_id = _to_int(item.get("id"), default=-1)
    if brief_id < 0:
        raise FrontendAPIError("Event brief data is incomplete.")
    brief = dict(item)
    brief["id"] = brief_id
    brief["event_id"] = _to_int(item.get("event_id"), 0)
    brief["snapshot_id"] = _to_int(item.get("snapshot_id"), 0)
    brief["headline"] = _safe_text(item.get("headline")) or f"Event brief {brief_id}"
    brief["brief_status"] = _safe_text(item.get("brief_status")) or "draft"
    brief["generation_method"] = _safe_text(item.get("generation_method")) or "deterministic"
    for field in ["confirmed_points", "uncertainties", "watch_next", "evidence_document_ids", "evidence_items"]:
        brief[field] = item.get(field) if isinstance(item.get(field), list) else []
    brief["change_summary"] = item.get("change_summary") if isinstance(item.get("change_summary"), dict) else {}
    return brief


def parse_event_briefs_response(payload) -> list[dict]:
    if not isinstance(payload, list):
        raise FrontendAPIError("Event briefs response was malformed.")
    return [normalize_event_brief_payload(item) for item in payload]


def parse_event_brief_response(payload) -> dict:
    return normalize_event_brief_payload(payload)


def parse_event_snapshot_create_response(payload) -> dict:
    if not isinstance(payload, dict) or "snapshot" not in payload:
        raise FrontendAPIError("Snapshot response was malformed.")
    return {
        "status": _safe_text(payload.get("status")) or "ok",
        "reused": bool(payload.get("reused")),
        "snapshot": parse_event_snapshot_response(payload["snapshot"]),
    }


def parse_event_brief_generate_response(payload) -> dict:
    if not isinstance(payload, dict) or "brief" not in payload or "change" not in payload:
        raise FrontendAPIError("Event brief generation response was malformed.")
    return {
        "status": _safe_text(payload.get("status")) or "ok",
        "reused": bool(payload.get("reused")),
        "brief": parse_event_brief_response(payload["brief"]),
        "change": normalize_event_change_payload(payload["change"]),
    }


def event_source_count(event: dict) -> int:
    return max(
        _to_int(event.get("distinct_source_count"), 0),
        _to_int(event.get("distinct_publisher_count"), 0),
    )


def publisher_or_source_key(document: dict) -> str:
    explicit = _safe_text(document.get("publisher")) or _safe_text(document.get("source_name"))
    if explicit:
        return explicit.lower()
    url = _safe_text(document.get("url"))
    if not url:
        return ""
    try:
        from urllib.parse import urlparse as parse_url

        return parse_url(url).netloc.lower()
    except ValueError:
        return ""


def distinct_publisher_count(documents: list[dict]) -> int:
    return len({key for key in (publisher_or_source_key(document) for document in documents) if key})


def event_overview_metrics(events: list[dict], now=None) -> dict:
    from datetime import datetime, timedelta, timezone

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is not None:
        current_time = current_time.astimezone(timezone.utc).replace(tzinfo=None)
    recent_cutoff = current_time - timedelta(days=7)
    total_events = len(events)
    total_documents = sum(_to_int(event.get("related_document_count"), 0) for event in events)
    multi_document_events = sum(
        1 for event in events if _to_int(event.get("related_document_count"), 0) > 1
    )
    multi_source_events = sum(1 for event in events if event_source_count(event) > 1)
    recent_events = 0
    for event in events:
        parsed = _parse_datetime(event.get("last_seen_at"))
        if parsed is None:
            continue
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        if recent_cutoff <= parsed <= current_time:
            recent_events += 1
    return {
        "total_events": total_events,
        "total_documents": total_documents,
        "multi_document_events": multi_document_events,
        "multi_source_events": multi_source_events,
        "recently_updated_events": recent_events,
    }


def event_filter_options(events: list[dict], field: str) -> list[str]:
    return sorted({_safe_text(event.get(field)) for event in events if _safe_text(event.get(field))})


def filter_events(
    events: list[dict],
    *,
    text_query: str = "",
    statuses: list[str] | None = None,
    event_types: list[str] | None = None,
    countries: list[str] | None = None,
    languages: list[str] | None = None,
    min_documents: int = 0,
    multi_source_only: bool = False,
) -> list[dict]:
    query = _safe_text(text_query).lower()
    status_values = set(statuses or [])
    type_values = set(event_types or [])
    country_values = set(countries or [])
    language_values = set(languages or [])
    minimum_documents = max(_to_int(min_documents, 0), 0)

    filtered = []
    for event in events:
        if query:
            haystack = f"{event.get('title', '')} {event.get('summary', '')}".lower()
            if query not in haystack:
                continue
        if status_values and event.get("status") not in status_values:
            continue
        if type_values and event.get("event_type") not in type_values:
            continue
        if country_values and event.get("country_or_region") not in country_values:
            continue
        if language_values and event.get("primary_language") not in language_values:
            continue
        if _to_int(event.get("related_document_count"), 0) < minimum_documents:
            continue
        if multi_source_only and event_source_count(event) <= 1:
            continue
        filtered.append(event)
    return filtered


def _datetime_sort_value(value) -> float:
    parsed = _parse_date_or_datetime(value)
    if parsed is None:
        return float("-inf")
    try:
        return parsed.timestamp()
    except (OSError, ValueError):
        return float("-inf")


def sort_events(events: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "First seen":
        return sorted(events, key=lambda event: _datetime_sort_value(event.get("first_seen_at")), reverse=True)
    if sort_by == "Document count":
        return sorted(events, key=lambda event: (_to_int(event.get("related_document_count"), 0), event.get("title", "").lower()), reverse=True)
    if sort_by == "Source or publisher count":
        return sorted(events, key=lambda event: (event_source_count(event), event.get("title", "").lower()), reverse=True)
    if sort_by == "Title":
        return sorted(events, key=lambda event: event.get("title", "").lower())
    return sorted(events, key=lambda event: _datetime_sort_value(event.get("last_seen_at")), reverse=True)


def timeline_sort_value(document: dict) -> float:
    published = _datetime_sort_value(document.get("published_date"))
    if published != float("-inf"):
        return published
    return _datetime_sort_value(document.get("fetched_at"))


def timeline_documents(documents: list[dict]) -> list[dict]:
    return sorted(documents, key=timeline_sort_value)


def _session_cache():
    streamlit = globals().get("st")
    if streamlit is None:
        return None
    return streamlit.session_state.setdefault("event_api_cache", {})


def _cached_event_fetch(cache_key: str, fetcher, *, force_refresh: bool = False, ttl_seconds: int = 30):
    cache = _session_cache()
    if cache is None:
        return fetcher()

    import time

    now = time.time()
    cached = cache.get(cache_key)
    if not force_refresh and cached and now - cached["timestamp"] < ttl_seconds:
        return cached["data"]

    data = fetcher()
    cache[cache_key] = {"timestamp": now, "data": data}
    return data


def clear_event_cache(event_id: int | None = None) -> None:
    cache = _session_cache()
    if cache is None:
        return
    if event_id is None:
        cache.clear()
        return
    for key in [
        "events:list",
        f"events:detail:{event_id}",
        f"events:documents:{event_id}",
        f"events:snapshots:{event_id}",
        f"events:snapshot_latest:{event_id}",
        f"events:changes:{event_id}",
        f"events:briefs:{event_id}",
    ]:
        cache.pop(key, None)


def get_events(force_refresh: bool = False) -> list[dict]:
    return _cached_event_fetch(
        "events:list",
        lambda: parse_event_list_response(api_get("/events")),
        force_refresh=force_refresh,
    )


def get_event(event_id: int, force_refresh: bool = False) -> dict:
    return _cached_event_fetch(
        f"events:detail:{event_id}",
        lambda: parse_event_detail_response(api_get(f"/events/{event_id}")),
        force_refresh=force_refresh,
    )


def get_event_documents(event_id: int, force_refresh: bool = False) -> list[dict]:
    return _cached_event_fetch(
        f"events:documents:{event_id}",
        lambda: parse_event_documents_response(api_get(f"/events/{event_id}/documents")),
        force_refresh=force_refresh,
    )


def recluster_document(document_id: int) -> dict:
    payload = api_post(f"/events/recluster/{document_id}", timeout=60)
    if not isinstance(payload, dict):
        raise FrontendAPIError("Reclustering response was malformed.")
    if payload.get("status") != "ok":
        raise FrontendAPIError("Reclustering did not complete.")
    return payload


def get_event_snapshots(event_id: int, force_refresh: bool = False) -> list[dict]:
    return _cached_event_fetch(
        f"events:snapshots:{event_id}",
        lambda: parse_event_snapshots_response(api_get(f"/events/{event_id}/snapshots")),
        force_refresh=force_refresh,
    )


def get_latest_event_snapshot(event_id: int, force_refresh: bool = False) -> dict | None:
    def fetch_latest():
        try:
            return parse_event_snapshot_response(api_get(f"/events/{event_id}/snapshots/latest"))
        except FrontendAPIError as exc:
            if "No event snapshot exists" in exc.message:
                return None
            raise

    return _cached_event_fetch(
        f"events:snapshot_latest:{event_id}",
        fetch_latest,
        force_refresh=force_refresh,
    )


def get_event_changes(event_id: int, force_refresh: bool = False) -> dict | None:
    def fetch_changes():
        try:
            return normalize_event_change_payload(api_get(f"/events/{event_id}/changes"))
        except FrontendAPIError as exc:
            if "No event snapshot exists" in exc.message:
                return None
            raise

    return _cached_event_fetch(
        f"events:changes:{event_id}",
        fetch_changes,
        force_refresh=force_refresh,
    )


def get_event_briefs(event_id: int, force_refresh: bool = False) -> list[dict]:
    return _cached_event_fetch(
        f"events:briefs:{event_id}",
        lambda: parse_event_briefs_response(api_get(f"/events/{event_id}/briefs")),
        force_refresh=force_refresh,
    )


def create_event_snapshot(event_id: int, *, force: bool = False) -> dict:
    return parse_event_snapshot_create_response(
        api_post(f"/events/{event_id}/snapshots", timeout=60, payload=None)
        if not force
        else api_post(f"/events/{event_id}/snapshots?force=true", timeout=60, payload=None)
    )


def generate_event_brief(event_id: int, *, force: bool = False) -> dict:
    return parse_event_brief_generate_response(
        api_post(f"/events/{event_id}/briefs/generate", timeout=120, payload=None)
        if not force
        else api_post(f"/events/{event_id}/briefs/generate?force=true", timeout=120, payload=None)
    )


def format_signed_delta(value: int, singular: str, plural: str | None = None) -> str:
    count = _to_int(value, 0)
    label = singular if abs(count) == 1 else (plural or f"{singular}s")
    sign = "+" if count > 0 else ""
    return f"{sign}{count} {label}"


def snapshot_history_change_level(previous_snapshot: dict | None, current_snapshot: dict) -> str:
    if previous_snapshot is None:
        return "baseline"
    if previous_snapshot.get("snapshot_hash") == current_snapshot.get("snapshot_hash"):
        return "none"

    previous_documents = set(previous_snapshot.get("document_ids") or [])
    current_documents = set(current_snapshot.get("document_ids") or [])
    previous_publishers = set(previous_snapshot.get("publisher_names") or [])
    current_publishers = set(current_snapshot.get("publisher_names") or [])
    previous_sources = set(previous_snapshot.get("source_names") or [])
    current_sources = set(current_snapshot.get("source_names") or [])

    new_documents = current_documents - previous_documents
    new_publishers = current_publishers - previous_publishers
    new_sources = current_sources - previous_sources
    metadata_changed = any(
        previous_snapshot.get(field) != current_snapshot.get(field)
        for field in ["event_status", "event_type", "country_or_region", "primary_language", "event_summary"]
    )

    if len(new_publishers) + len(new_sources) >= 3 and (metadata_changed or len(new_documents) >= 3):
        return "major"
    if metadata_changed or new_publishers or new_sources or len(new_documents) >= 3:
        return "meaningful"
    if new_documents:
        return "minor"
    return "none"


def get_api_error_detail(exc: Exception) -> str:
    if isinstance(exc, FrontendAPIError):
        return exc.message
    response = getattr(exc, "response", None)
    if response is None:
        return _concise_error(str(exc), "Request failed.")

    try:
        payload = response.json()
    except ValueError:
        return _concise_error(response.text, "Request failed.")

    detail = payload.get("detail") if isinstance(payload, dict) else None
    return _concise_error(str(detail or payload or exc), "Request failed.")



if page == "Start Here":
    st.subheader("Start Here")
    st.caption("Demo Polish Edition: guided workflow for non-technical users and portfolio demos.")

    st.write("### What this app does")
    st.markdown(
        """
        This app helps a policy/public diplomacy team:

        1. load a curated approved-source library,
        2. ingest public AI governance sources,
        3. search across retrieved source chunks,
        4. generate structured policy briefs,
        5. review and export those briefs,
        6. keep an audit trail.
        """
    )

    st.write("### Recommended demo path")

    steps = [
        ("1", "System Status", "Initialize database tables."),
        ("2", "Source Pack", "Load curated sources into the Source Library."),
        ("3", "Source Pack", "Batch ingest the recommended first 3 sources."),
        ("4", "Documents", "Create chunks and prepare searchable chunks."),
        ("5", "Ask Knowledge Base", "Ask: What is the NIST AI Risk Management Framework?"),
        ("6", "Generate Brief", "Generate a structured policy brief."),
        ("7", "Review Briefs", "Set status to reviewed or needs_senior_review."),
        ("8", "Export Brief", "Export the brief as Markdown."),
        ("9", "Dashboard", "Show updated governance metrics."),
        ("10", "Audit Logs", "Show traceability of actions."),
    ]

    st.dataframe(
        [{"Step": s, "Page": p, "Action": a} for s, p, a in steps],
        use_container_width=True,
    )

    st.write("### One-click demo setup helper")

    st.info(
        "This loads curated sources and ingests the first recommended demo sources. "
        "You still need to prepare chunks in the Documents page before asking questions."
    )

    if st.button("Run demo setup"):
        try:
            with st.spinner("Loading curated sources and ingesting recommended demo sources..."):
                result = api_post("/admin/demo-setup")
            st.success(result["message"])
            st.json(result)
        except Exception as exc:
            st.error("Demo setup failed. Make sure the database has been initialized from System Status.")
            st.code(str(exc))

    st.write("### Recommended first questions")

    st.code(
        """What is the NIST AI Risk Management Framework?
What are the main functions of the AI RMF?
How does the EU AI Act use a risk-based approach?
Why does AI governance matter for public diplomacy?"""
    )

elif page == "Dashboard":

    st.subheader("Operational Dashboard")
    st.caption("Phase 8: quick overview of source coverage, retrieval readiness, brief status and recent audit activity.")

    try:
        metrics = api_get("/dashboard/metrics")
        totals = metrics["totals"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Sources", totals["sources"])
        c2.metric("Documents", totals["documents"])
        c3.metric("Chunks", totals["chunks"])

        c4, c5, c6 = st.columns(3)
        c4.metric("Searchable chunks", totals["searchable_chunks"])
        c5.metric("Briefs", totals["briefs"])
        c6.metric("Audit logs", totals["audit_logs"])

        st.write("### Source Governance")
        g1, g2 = st.columns(2)
        with g1:
            st.write("Sources by reliability")
            st.dataframe(
                [{"reliability_tier": k, "count": v} for k, v in metrics["sources_by_reliability"].items()],
                use_container_width=True,
            )
        with g2:
            st.write("Sources by type")
            st.dataframe(
                [{"source_type": k, "count": v} for k, v in metrics["sources_by_type"].items()],
                use_container_width=True,
            )

        st.write("### Brief Governance")
        b1, b2 = st.columns(2)
        with b1:
            st.write("Briefs by review status")
            st.dataframe(
                [{"review_status": k, "count": v} for k, v in metrics["briefs_by_status"].items()],
                use_container_width=True,
            )
        with b2:
            st.write("Briefs by sensitivity")
            st.dataframe(
                [{"sensitivity": k, "count": v} for k, v in metrics["briefs_by_sensitivity"].items()],
                use_container_width=True,
            )

        st.write("### Documents by Sensitivity")
        st.dataframe(
            [{"sensitivity": k, "count": v} for k, v in metrics["documents_by_sensitivity"].items()],
            use_container_width=True,
        )

        st.write("### Recent Audit Activity")
        st.dataframe(metrics["recent_audit_logs"], use_container_width=True)

    except Exception as exc:
        st.error("Could not load dashboard metrics.")
        st.code(str(exc))

elif page == "Events":
    st.subheader("Events")
    st.caption("Event-oriented view of media intelligence. Documents remain the supporting evidence layer.")

    refresh_col, note_col = st.columns([1, 4])
    with refresh_col:
        if st.button("Refresh event data"):
            clear_event_cache()
            st.session_state.pop("selected_event_id", None)
            st.success("Event data refreshed.")
    with note_col:
        st.info("Event data is loaded from the backend API. Run event backfill if no events are shown.")

    try:
        with st.spinner("Loading events..."):
            events = get_events()
    except Exception as exc:
        st.error(get_api_error_detail(exc))
        st.info("Confirm that the backend is running on the configured API URL, then refresh event data.")
        events = []

    if not events:
        st.info("No events yet. Ingest documents and run the event backfill to populate event intelligence.")
    else:
        metrics = event_overview_metrics(events)
        metric_cols = st.columns(5)
        metric_cols[0].metric("Events", metrics["total_events"])
        metric_cols[1].metric("Related documents", metrics["total_documents"])
        metric_cols[2].metric("Multi-document events", metrics["multi_document_events"])
        metric_cols[3].metric("Multi-source events", metrics["multi_source_events"])
        metric_cols[4].metric("Updated in 7 days", metrics["recently_updated_events"])

        st.write("### Filters")
        if st.button("Reset filters"):
            for key, value in {
                "event_text_filter": "",
                "event_status_filter": [],
                "event_type_filter": [],
                "event_region_filter": [],
                "event_language_filter": [],
                "event_min_documents": 0,
                "event_multi_source_only": False,
                "event_sort_by": "Newest activity",
            }.items():
                st.session_state[key] = value
            st.rerun()

        filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
        with filter_col_1:
            text_query = st.text_input("Search title or summary", key="event_text_filter")
            statuses = st.multiselect(
                "Status",
                event_filter_options(events, "status"),
                key="event_status_filter",
            )
            min_documents = st.number_input(
                "Minimum related documents",
                min_value=0,
                step=1,
                key="event_min_documents",
            )
        with filter_col_2:
            event_types = st.multiselect(
                "Event type",
                event_filter_options(events, "event_type"),
                key="event_type_filter",
            )
            countries = st.multiselect(
                "Country or region",
                event_filter_options(events, "country_or_region"),
                key="event_region_filter",
            )
            multi_source_only = st.checkbox("Multi-source events only", key="event_multi_source_only")
        with filter_col_3:
            languages = st.multiselect(
                "Language",
                event_filter_options(events, "primary_language"),
                key="event_language_filter",
            )
            sort_by = st.selectbox(
                "Sort by",
                [
                    "Newest activity",
                    "First seen",
                    "Document count",
                    "Source or publisher count",
                    "Title",
                ],
                key="event_sort_by",
            )

        filtered_events = filter_events(
            events,
            text_query=text_query,
            statuses=statuses,
            event_types=event_types,
            countries=countries,
            languages=languages,
            min_documents=min_documents,
            multi_source_only=multi_source_only,
        )
        sorted_filtered_events = sort_events(filtered_events, sort_by)

        st.write("### Event List")
        st.caption(f"Showing {len(sorted_filtered_events)} of {len(events)} events.")

        if not sorted_filtered_events:
            st.warning("No events match the current filters.")
        else:
            for event in sorted_filtered_events:
                st.markdown("---")
                title_col, action_col = st.columns([5, 1])
                with title_col:
                    st.write(f"#### {event['title']}")
                    if event.get("summary"):
                        st.write(event["summary"])

                    metadata = []
                    for label, field in [
                        ("Type", "event_type"),
                        ("Status", "status"),
                        ("Region", "country_or_region"),
                        ("Language", "primary_language"),
                    ]:
                        if event.get(field):
                            metadata.append(f"**{label}:** {event[field]}")
                    if event.get("first_seen_at"):
                        metadata.append(f"**First seen:** {format_datetime_value(event.get('first_seen_at'))}")
                    if event.get("last_seen_at"):
                        metadata.append(f"**Last seen:** {format_datetime_value(event.get('last_seen_at'))}")
                    if metadata:
                        st.markdown(" | ".join(metadata))

                    coverage = [
                        format_count(event.get("related_document_count"), "related document"),
                        format_count(event_source_count(event), "distinct publisher"),
                    ]
                    if event_source_count(event) > 1:
                        coverage.append("Reported by multiple sources")
                    st.caption(" | ".join(coverage))
                with action_col:
                    if st.button("Open", key=f"open_event_{event['id']}"):
                        st.session_state["selected_event_id"] = event["id"]

        selected_event_id = st.session_state.get("selected_event_id")
        if selected_event_id:
            st.markdown("---")
            try:
                with st.spinner("Loading event detail..."):
                    event_detail = get_event(selected_event_id)
                    event_documents = get_event_documents(selected_event_id)
            except Exception as exc:
                st.error(get_api_error_detail(exc))
                st.info("Refresh event data and confirm that the selected event still exists.")
                event_detail = None
                event_documents = []

            if event_detail:
                st.write("### Event Detail")
                st.write(f"#### {event_detail['title']}")
                if event_detail.get("summary"):
                    st.write(event_detail["summary"])

                source_count = distinct_publisher_count(event_documents)
                detail_cols = st.columns(4)
                detail_cols[0].metric("Related documents", len(event_documents))
                detail_cols[1].metric("Distinct publishers", source_count)
                detail_cols[2].metric("First seen", format_datetime_value(event_detail.get("first_seen_at")))
                detail_cols[3].metric("Last seen", format_datetime_value(event_detail.get("last_seen_at")))

                metadata_rows = []
                for label, field in [
                    ("Event type", "event_type"),
                    ("Status", "status"),
                    ("Country or region", "country_or_region"),
                    ("Primary language", "primary_language"),
                ]:
                    if event_detail.get(field):
                        metadata_rows.append({"Field": label, "Value": event_detail[field]})
                if metadata_rows:
                    st.write("#### Event-level metadata")
                    st.dataframe(metadata_rows, use_container_width=True, hide_index=True)

                st.write("#### Event Intelligence")
                try:
                    latest_snapshot = get_latest_event_snapshot(selected_event_id)
                    latest_change = get_event_changes(selected_event_id) if latest_snapshot else None
                    event_briefs = get_event_briefs(selected_event_id)
                    event_snapshots = get_event_snapshots(selected_event_id)
                except Exception as exc:
                    st.error(get_api_error_detail(exc))
                    latest_snapshot = None
                    latest_change = None
                    event_briefs = []
                    event_snapshots = []

                intelligence_cols = st.columns(3)
                with intelligence_cols[0]:
                    if st.button("Create snapshot"):
                        try:
                            with st.spinner("Creating event snapshot..."):
                                result = create_event_snapshot(selected_event_id)
                            clear_event_cache(selected_event_id)
                            message = "Snapshot reused." if result["reused"] else "Snapshot created."
                            st.success(f"{message} Snapshot ID {result['snapshot']['id']}.")
                            st.rerun()
                        except Exception as exc:
                            st.error(get_api_error_detail(exc))
                with intelligence_cols[1]:
                    if st.button("Generate event brief"):
                        try:
                            with st.spinner("Generating event brief..."):
                                result = generate_event_brief(selected_event_id)
                            clear_event_cache(selected_event_id)
                            message = "Existing event brief reused." if result["reused"] else "Event brief generated."
                            st.success(f"{message} Brief ID {result['brief']['id']}.")
                            st.rerun()
                        except Exception as exc:
                            st.error(get_api_error_detail(exc))
                with intelligence_cols[2]:
                    if st.button("Refresh intelligence"):
                        clear_event_cache(selected_event_id)
                        st.success("Event intelligence refreshed.")
                        st.rerun()

                if latest_snapshot:
                    state_cols = st.columns(4)
                    state_cols[0].metric("Latest snapshot", format_datetime_value(latest_snapshot.get("created_at")))
                    state_cols[1].metric("Snapshot documents", latest_snapshot.get("document_count", 0))
                    state_cols[2].metric("Snapshot publishers", latest_snapshot.get("distinct_publisher_count", 0))
                    state_cols[3].metric(
                        "Change level",
                        (latest_change or {}).get("change_level", "Not available"),
                    )

                    if latest_change:
                        change_cols = st.columns(3)
                        change_cols[0].metric(
                            "New documents",
                            format_signed_delta(len(latest_change.get("new_document_ids", [])), "document"),
                        )
                        change_cols[1].metric(
                            "New sources",
                            format_signed_delta(len(latest_change.get("new_sources", [])), "source"),
                        )
                        change_cols[2].metric(
                            "New publishers",
                            format_signed_delta(len(latest_change.get("new_publishers", [])), "publisher"),
                        )
                        if latest_change.get("is_initial_baseline"):
                            st.info("Initial event baseline - no previous snapshot is available for comparison.")
                        elif latest_change.get("change_level") == "none":
                            st.info("No meaningful change detected since the previous snapshot.")
                        else:
                            st.info(latest_change.get("deterministic_change_summary") or "No change summary available.")
                    else:
                        st.info("Initial event baseline - no previous snapshot is available for comparison.")
                else:
                    st.info("No event snapshot exists yet. Use Create snapshot to establish the first baseline.")

                latest_brief = event_briefs[0] if event_briefs else None
                if latest_brief:
                    st.write("##### Latest Event Brief")
                    st.caption(
                        f"Status: {latest_brief.get('brief_status')} | "
                        f"Generation: {latest_brief.get('generation_method')} | "
                        f"Created: {format_datetime_value(latest_brief.get('created_at'))}"
                    )
                    st.write(f"**{latest_brief['headline']}**")
                    for label, field in [
                        ("What happened", "what_happened"),
                        ("What changed", "what_changed"),
                        ("Why it matters", "why_it_matters"),
                    ]:
                        if latest_brief.get(field):
                            st.write(f"**{label}**")
                            st.write(latest_brief[field])
                    for label, field in [
                        ("Confirmed", "confirmed_points"),
                        ("Uncertainties", "uncertainties"),
                        ("What to watch next", "watch_next"),
                    ]:
                        values = latest_brief.get(field) or []
                        if values:
                            st.write(f"**{label}**")
                            for value in values:
                                st.write(f"- {value}")
                    evidence_rows = []
                    for item in latest_brief.get("evidence_items", []):
                        evidence_rows.append(
                            {
                                "Document ID": item.get("document_id"),
                                "Title": item.get("title"),
                                "Publisher": item.get("publisher") or item.get("source_name") or format_missing(),
                                "Published": format_date_value(item.get("published_date")),
                                "URL": item.get("url"),
                            }
                        )
                    if evidence_rows:
                        st.write("**Evidence**")
                        st.dataframe(evidence_rows, use_container_width=True, hide_index=True)
                        with st.expander("Evidence links"):
                            for item in latest_brief.get("evidence_items", []):
                                if item.get("url"):
                                    title = item.get("title") or f"Document {item.get('document_id')}"
                                    st.markdown(f"- [{title}]({item['url']})")
                else:
                    st.info("No event brief exists yet. Use Generate event brief after creating a snapshot.")

                if event_snapshots or event_briefs:
                    with st.expander("Snapshot and brief history"):
                        brief_status_by_snapshot = {
                            brief.get("snapshot_id"): brief.get("brief_status")
                            for brief in event_briefs
                        }
                        history_rows = []
                        snapshots_ascending = sorted(
                            event_snapshots,
                            key=lambda item: _datetime_sort_value(item.get("created_at")),
                        )
                        history_change_by_id = {}
                        previous_snapshot = None
                        for snapshot in snapshots_ascending:
                            history_change_by_id[snapshot.get("id")] = snapshot_history_change_level(
                                previous_snapshot,
                                snapshot,
                            )
                            previous_snapshot = snapshot
                        for snapshot in event_snapshots:
                            history_rows.append(
                                {
                                    "Snapshot": snapshot.get("id"),
                                    "Created": format_datetime_value(snapshot.get("created_at")),
                                    "Documents": snapshot.get("document_count", 0),
                                    "Publishers": snapshot.get("distinct_publisher_count", 0),
                                    "Change": history_change_by_id.get(snapshot.get("id"), "not available"),
                                    "Brief status": brief_status_by_snapshot.get(snapshot.get("id"), "No brief"),
                                }
                            )
                        if history_rows:
                            st.dataframe(history_rows, use_container_width=True, hide_index=True)

                st.write("#### Supporting documents and evidence")
                if not event_documents:
                    st.info("This event has no related documents yet.")
                else:
                    st.caption(
                        f"{format_count(len(event_documents), 'related document')} | "
                        f"{format_count(source_count, 'distinct publisher')}"
                    )
                    if source_count > 1:
                        st.info("Reported by multiple sources. This does not by itself prove source independence.")

                    for document in event_documents:
                        label_parts = [document["document_title"]]
                        source_label = document.get("publisher") or document.get("source_name")
                        if source_label:
                            label_parts.append(source_label)
                        with st.expander(" | ".join(label_parts)):
                            doc_cols = st.columns(2)
                            with doc_cols[0]:
                                if source_label:
                                    st.write(f"**Source / publisher:** {source_label}")
                                if document.get("published_date"):
                                    st.write(f"**Published:** {format_date_value(document.get('published_date'))}")
                                if document.get("fetched_at"):
                                    st.write(f"**Fetched:** {format_datetime_value(document.get('fetched_at'))}")
                                if document.get("url"):
                                    st.markdown(f"**URL:** [{document['url']}]({document['url']})")
                            with doc_cols[1]:
                                st.write(f"**Relationship:** {relationship_type_label(document.get('relationship_type'))}")
                                st.write(f"**Clustering:** {clustering_method_label(document.get('clustering_method'))}")
                                st.write(f"**Similarity:** {format_similarity_score(document.get('similarity_score'))}")
                            with st.expander("Advanced technical values"):
                                st.write(f"Document ID: {document['document_id']}")
                                st.write(f"Event ID: {document.get('event_id')}")
                                st.write(f"Relationship type: {readable_value(document.get('relationship_type'))}")
                                st.write(f"Clustering method: {readable_value(document.get('clustering_method'))}")
                                st.write(f"Similarity score: {readable_value(document.get('similarity_score'))}")

                    st.write("#### Source timeline")
                    timeline_rows = []
                    for document in timeline_documents(event_documents):
                        timeline_date = document.get("published_date") or document.get("fetched_at")
                        timeline_rows.append(
                            {
                                "Date": format_date_value(timeline_date),
                                "Basis": "Published" if document.get("published_date") else "Fetched",
                                "Source / publisher": document.get("publisher") or document.get("source_name") or format_missing(),
                                "Document": document["document_title"],
                                "Clustering": clustering_method_label(document.get("clustering_method")),
                                "Similarity": format_similarity_score(document.get("similarity_score")),
                            }
                        )
                    st.dataframe(timeline_rows, use_container_width=True, hide_index=True)

                    with st.expander("Advanced"):
                        recluster_document_id = st.selectbox(
                            "Document to recluster",
                            [document["document_id"] for document in event_documents],
                            format_func=lambda doc_id: next(
                                (
                                    f"{document['document_id']} - {document['document_title']}"
                                    for document in event_documents
                                    if document["document_id"] == doc_id
                                ),
                                str(doc_id),
                            ),
                        )
                        if st.button("Recluster selected document"):
                            try:
                                result = recluster_document(recluster_document_id)
                                clear_event_cache(selected_event_id)
                                clear_event_cache(result.get("event_id"))
                                clear_event_cache(None)
                                st.success(
                                    "Reclustering completed: "
                                    f"{clustering_method_label(result.get('clustering_method'))} "
                                    f"({format_similarity_score(result.get('similarity_score'))})."
                                )
                            except Exception as exc:
                                st.error(get_api_error_detail(exc))

elif page == "System Status":

    st.subheader("System status")
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=5)
        st.success("Backend is running." if r.ok else f"Backend status: {r.status_code}")
        st.json(r.json())
    except Exception as exc:
        st.warning("Backend is not reachable yet.")
        st.code(str(exc))
    if st.button("Initialize database tables"):
        try: st.success(api_post("/admin/init-db")["message"])
        except Exception as exc: st.error("Could not initialize database."); st.code(str(exc))

elif page == "Sources":
    st.subheader("Approved Source Library")
    try:
        existing_sources = api_get("/sources")
    except Exception:
        existing_sources = []

    with st.form("create_source_form"):
        name = st.text_input("Source name", value="European Commission - AI")
        base_url = st.text_input("Base URL", value="https://digital-strategy.ec.europa.eu/")
        source_type = st.selectbox("Source type", ["official", "think_tank", "media", "company", "academic", "other"])
        reliability_tier = st.selectbox("Reliability tier", ["high", "medium", "low"])
        country_or_institution = st.text_input("Country / institution", value="EU")
        notes = st.text_area("Notes", value="Official EU digital policy source.")
        is_active = st.checkbox("Active", value=True)
        if st.form_submit_button("Add source"):
            try:
                existing_source = find_source_by_name(existing_sources, name)
                if existing_source:
                    result = existing_source
                    st.info(f"Using existing source ID {result['id']}: {result['name']}")
                else:
                    result = api_post(
                        "/sources",
                        build_source_create_payload(
                            name=name,
                            base_url=base_url,
                            source_type=source_type,
                            reliability_tier=reliability_tier,
                            country_or_institution=country_or_institution,
                            notes=notes,
                            is_active=is_active,
                        ),
                    )
                    st.success(f"Source ready: {result['name']} (ID {result['id']})")
                st.json(result)
            except Exception as exc:
                st.error("Could not create or reuse source.")
                st.code(get_api_error_detail(exc))
    try: st.dataframe(api_get("/sources"), use_container_width=True)
    except Exception as exc: st.warning("Could not load sources."); st.code(str(exc))



elif page == "Source Pack":
    st.subheader("Curated Source Pack")
    st.caption("Phase 8: approved seed sources with reliability tiers and policy metadata.")

    if st.button("Load curated sources into Source Library"):
        try:
            result = api_post("/admin/load-seed-sources")
            st.success(
                f"Seed sources loaded. Created: {result['created']} | "
                f"Existing: {result['existing']} | Total: {result['total_seed_sources']}"
            )
        except Exception as exc:
            st.error("Could not load seed sources.")
            st.code(str(exc))

    try:
        seed_sources = api_get("/admin/seed-sources")
        seed_names = [item["name"] for item in seed_sources]

        recommended = [item for item in seed_sources if item.get("demo_recommended") is True]
        st.write(f"Curated seed sources: {len(seed_sources)}")
        st.write("### Recommended stable demo sources")
        st.dataframe(recommended, use_container_width=True)
        st.dataframe(seed_sources, use_container_width=True)

        st.write("### Batch ingest curated sources")
        selected_batch = st.multiselect(
            "Select multiple seed sources",
            seed_names,
            default=seed_names[:3] if len(seed_names) >= 3 else seed_names,
        )

        if st.button("Batch ingest selected seed sources"):
            if not selected_batch:
                st.warning("Select at least one seed source.")
            else:
                try:
                    with st.spinner("Batch ingesting selected seed sources..."):
                        batch_result = api_post(
                            "/admin/ingest-seed-sources-batch",
                            {"seed_names": selected_batch},
                        )
                    st.success(
                        f"Batch complete. Successful/existing: {batch_result['successful_or_existing']} | "
                        f"Failed: {batch_result['failed']}"
                    )
                    st.dataframe(batch_result["results"], use_container_width=True)
                except Exception as exc:
                    st.error("Batch ingestion failed.")
                    st.code(str(exc))

        st.write("### Ingest one curated source")
        selected_seed = st.selectbox("Seed source", seed_names)

        if st.button("Ingest selected seed source"):
            try:
                with st.spinner("Ingesting selected seed source..."):
                    result = requests.post(
                        f"{API_BASE_URL}/admin/ingest-seed-source",
                        params={"seed_name": selected_seed},
                        timeout=120,
                    )
                    result.raise_for_status()
                    payload = result.json()
                st.success(f"Seed source status: {payload['status']}")
                st.json(payload)
            except Exception as exc:
                st.error("Could not ingest selected seed source.")
                st.code(str(exc))

    except Exception as exc:
        st.error("Could not load curated source pack.")
        st.code(str(exc))


elif page == "Ingest URL":
    st.subheader("Ingest a public URL")
    try: sources = api_get("/sources")
    except Exception: sources = []
    source_options = {NO_SOURCE_SELECTED_LABEL: None} | {
        f"Source ID {s['id']}: {s['name']} ({s['reliability_tier']})": s["id"]
        for s in sources
    }
    with st.form("ingest_url_form"):
        url = st.text_input("Public URL", value="https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai")
        source_label = st.selectbox("Source", list(source_options.keys()))
        topic_tags = st.text_input("Topic tags", value="EU AI Act, AI governance, regulation")
        sensitivity_level = st.selectbox("Sensitivity level", ["low", "medium", "high", "critical"], index=1)
        language = st.text_input("Language", value="English")
        if st.form_submit_button("Ingest URL"):
            try:
                with st.spinner("Extracting and saving document..."):
                    st.json(api_post(
                        "/ingest/url",
                        build_url_ingest_payload(
                            url=url,
                            source_id=source_options[source_label],
                            topic_tags=topic_tags,
                            sensitivity_level=sensitivity_level,
                            language=language,
                        ),
                    ))
                st.success("Document ingested.")
            except Exception as exc:
                st.error("Could not ingest URL.")
                st.code(get_api_error_detail(exc))


elif page == "Documents":
    st.subheader("Documents")
    try:
        docs = api_get("/documents")
        st.write(f"Documents: {len(docs)}")
        st.dataframe(docs, use_container_width=True)

        if docs:
            selected_id = st.selectbox("Select document", [d["id"] for d in docs])

            if st.button("Check chunk status"):
                try:
                    status = api_get(f"/documents/{selected_id}/chunk-status")
                    st.info(
                        f"Document status: {status['status']} | "
                        f"Chunks: {status['chunk_count']} | "
                        f"Searchable/embedded chunks: {status['embedded_count']}"
                    )
                except Exception as exc:
                    st.error("Could not load chunk status.")
                    st.code(str(exc))

            c1, c2, c3 = st.columns(3)

            if c1.button("Load preview"):
                st.session_state["detail"] = api_get(f"/documents/{selected_id}")

            if c2.button("Create chunks / check existing chunks"):
                try:
                    result = api_post(f"/documents/{selected_id}/chunk")
                    st.success(f"Chunks ready: {result['chunks_created']} chunks.")
                except Exception as exc:
                    st.error("Could not create/check chunks.")
                    st.code(str(exc))

            if c3.button("Generate embeddings"):
                try:
                    with st.spinner("Preparing searchable chunks..."):
                        result = api_post(f"/documents/{selected_id}/embed")
                    st.success(f"Prepared searchable representations for {result['chunks_created']} chunks.")
                except Exception as exc:
                    st.error("Could not generate embeddings.")
                    st.code(str(exc))

            if st.session_state.get("detail"):
                d = st.session_state["detail"]
                st.write(f"### {d['title']}")
                st.write(d["url"])
                st.text_area("Cleaned text preview", d.get("cleaned_text") or "", height=350)

    except Exception as exc:
        st.warning("Could not load documents. Please initialize the database and ingest at least one source first.")
        st.code(str(exc))


elif page == "Semantic Search":
    st.subheader("Semantic Search")
    query = st.text_input("Question / search query", value="What is the EU risk-based approach to AI regulation?")
    top_k = st.slider("Top K results", 1, 10, 5)
    if st.button("Search"):
        try:
            result = api_get("/search", params={"query": query, "top_k": top_k})
            st.write(f"Results: {len(result['results'])}")
            for i,item in enumerate(result["results"],1):
                dist = item['distance'] if item['distance'] is not None else 0
                with st.expander(f"{i}. {item['title']} | distance={dist:.4f}"):
                    st.write(f"**Source:** {item.get('source_name')} ({item.get('reliability_tier')})")
                    st.write(f"**URL:** {item['url']}")
                    st.write(f"**Document ID:** {item['document_id']} | **Chunk ID:** {item['chunk_id']}")
                    st.text_area("Chunk content", item["content"], height=220)
        except Exception as exc: st.error("Search failed."); st.code(str(exc))


elif page == "Ask Knowledge Base":
    st.subheader("Ask Knowledge Base")
    st.caption("Phase 4: retrieves relevant chunks and generates a source-grounded answer. Local mode uses an extractive answer; OpenAI mode can generate a polished synthesis.")

    question = st.text_input(
        "Question",
        value="What is the NIST AI Risk Management Framework?",
    )
    top_k = st.slider("Number of source chunks", min_value=1, max_value=10, value=5)

    if st.button("Generate answer"):
        try:
            with st.spinner("Retrieving sources and generating answer..."):
                result = api_post("/rag/answer", {"question": question, "top_k": top_k})

            st.write("### Answer")
            st.markdown(result["answer"])

            st.info(
                f"Answer provider: {result['answer_provider']} | "
                f"Retrieval provider: {result['retrieval_provider']}"
            )

            st.write("### Sources")
            for citation in result["citations"]:
                with st.expander(f"{citation['citation_id']} {citation['title']}"):
                    st.write(f"**URL:** {citation['url']}")
                    st.write(f"**Source:** {citation.get('source_name')} ({citation.get('reliability_tier')})")
                    st.write(f"**Document ID:** {citation['document_id']} | **Chunk ID:** {citation['chunk_id']}")
                    st.text_area("Excerpt", citation["excerpt"], height=180)
        except Exception as exc:
            st.error("Could not generate answer.")
            st.code(str(exc))



elif page == "Generate Brief":
    st.subheader("Generate Policy Brief")
    st.caption("Phase 5: creates a structured AI foreign policy/public diplomacy brief from retrieved source chunks.")

    topic = st.text_input(
        "Brief topic",
        value="NIST AI Risk Management Framework and AI governance",
    )
    audience = st.text_input(
        "Audience",
        value="public diplomacy and policy team",
    )
    top_k = st.slider("Number of source chunks", min_value=1, max_value=10, value=6)

    if st.button("Generate policy brief"):
        try:
            with st.spinner("Retrieving sources and generating policy brief..."):
                result = api_post(
                    "/brief-generator/generate",
                    {"topic": topic, "audience": audience, "top_k": top_k},
                )

            st.success(f"Generated brief ID: {result.get('brief_id')}")
            st.info(
                f"Answer provider: {result['answer_provider']} | "
                f"Retrieval provider: {result['retrieval_provider']}"
            )

            st.write("### Brief")
            st.markdown(result["content"])

            st.write("### Retrieved Sources")
            for idx, item in enumerate(result["sources"], start=1):
                with st.expander(f"[{idx}] {item['title']}"):
                    st.write(f"**URL:** {item['url']}")
                    st.write(f"**Source:** {item.get('source_name')} ({item.get('reliability_tier')})")
                    st.write(f"**Document ID:** {item['document_id']} | **Chunk ID:** {item['chunk_id']}")
                    st.text_area("Source chunk", item["content"], height=180)
        except Exception as exc:
            st.error("Could not generate policy brief.")
            st.code(str(exc))



elif page == "Review Briefs":
    st.subheader("Review Briefs")
    st.caption("Phase 6: governance review workflow for generated policy briefs.")

    try:
        briefs = api_get("/briefs")
        if not briefs:
            st.info("No briefs yet. Generate a brief first.")
        else:
            selected_id = st.selectbox(
                "Select brief",
                [brief["id"] for brief in briefs],
                format_func=lambda x: next(
                    (f"{b['id']} — {b['title']} [{b['review_status']}]" for b in briefs if b["id"] == x),
                    str(x),
                ),
            )

            if st.button("Load brief"):
                st.session_state["review_brief_detail"] = api_get(f"/briefs/{selected_id}")

            detail = st.session_state.get("review_brief_detail")
            if detail and detail["id"] == selected_id:
                st.write(f"### {detail['title']}")
                st.info(
                    f"Status: {detail['review_status']} | "
                    f"Sensitivity: {detail['sensitivity_level']} | "
                    f"Confidence: {detail['confidence_level']}"
                )

                st.write("#### Brief Content")
                st.markdown(detail["content"])

                with st.expander("Sources / citation trail"):
                    for source in detail["sources"]:
                        st.write(f"**{source['citation_label']} {source.get('title')}**")
                        st.write(source.get("url"))
                        st.text_area(
                            f"Excerpt — chunk {source.get('chunk_id')}",
                            source.get("excerpt") or "",
                            height=120,
                        )

                st.write("#### Review decision")
                new_status = st.selectbox(
                    "Review status",
                    ["draft", "reviewed", "approved", "rejected", "needs_senior_review"],
                    index=["draft", "reviewed", "approved", "rejected", "needs_senior_review"].index(
                        detail["review_status"]
                    )
                    if detail["review_status"] in ["draft", "reviewed", "approved", "rejected", "needs_senior_review"]
                    else 0,
                )
                reviewer = st.text_input("Reviewer", value="demo_reviewer")
                notes = st.text_area("Reviewer notes", value=detail.get("reviewer_notes") or "")

                if st.button("Save review decision"):
                    try:
                        result = api_patch(
                            f"/briefs/{selected_id}/review",
                            {
                                "review_status": new_status,
                                "reviewer_notes": notes,
                                "reviewer": reviewer,
                            },
                        )
                        st.success(f"Updated review status to: {result['review_status']}")
                        st.session_state["review_brief_detail"] = api_get(f"/briefs/{selected_id}")
                    except Exception as exc:
                        st.error("Could not update review status.")
                        st.code(str(exc))
    except Exception as exc:
        st.error("Could not load review workflow.")
        st.code(str(exc))


elif page == "Briefs":
    st.subheader("Briefs")
    try: st.dataframe(api_get("/briefs"), use_container_width=True)
    except Exception as exc: st.warning("Could not load briefs."); st.code(str(exc))


elif page == "Export Brief":
    st.subheader("Export Brief")
    st.caption("Phase 8: export generated policy briefs as Markdown deliverables.")

    try:
        briefs = api_get("/briefs")
        if not briefs:
            st.info("No briefs available. Generate a brief first.")
        else:
            selected_id = st.selectbox(
                "Select brief to export",
                [brief["id"] for brief in briefs],
                format_func=lambda x: next(
                    (f"{b['id']} — {b['title']} [{b['review_status']}]" for b in briefs if b["id"] == x),
                    str(x),
                ),
            )

            if st.button("Export as Markdown"):
                try:
                    result = api_post(f"/export/brief/{selected_id}/markdown")
                    st.success(f"Exported: {result['filename']}")
                    st.write("### Markdown preview")
                    st.text_area("Exported Markdown", result["markdown"], height=500)
                    st.info(f"Local file path: {result['path']}")
                except Exception as exc:
                    st.error("Could not export brief.")
                    st.code(str(exc))
    except Exception as exc:
        st.error("Could not load briefs for export.")
        st.code(str(exc))


elif page == "Audit Logs":
    st.subheader("Audit Logs")
    try: st.dataframe(api_get("/audit-logs"), use_container_width=True)
    except Exception as exc: st.warning("Could not load audit logs."); st.code(str(exc))

elif page == "Governance":
    st.subheader("Governance controls")
    st.markdown("""
- **No source, no claim**
- **Public sources only**
- **Human review before external use**
- **Senior review for sensitive topics**
- **Source reliability tiers**
- **Audit logging**
- **Draft-only AI output**
        - **Citation-safe chunking: existing chunks are not deleted if already referenced by briefs**
        - **Brief review workflow: draft → reviewed → approved/rejected/needs senior review**
        - **Curated approved-source registry with reliability tiers**
        - **Operational dashboard for source, document, chunk, brief and audit coverage**
        - **Batch ingestion with per-source success/failure reporting**
        - **Markdown export for reviewable policy deliverables**
        - **Start Here onboarding workflow for non-technical demo users**
        - **Recommended stable demo sources for reliable first runs**
""")
    st.code("""URL -> Article extraction -> Text cleaning -> Document storage -> Chunking -> Embeddings -> pgvector semantic search -> RAG answer generation
  -> Brief generator
  -> Next: review workflow""")
