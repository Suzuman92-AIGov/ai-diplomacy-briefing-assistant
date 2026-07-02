import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_APP = PROJECT_ROOT / "frontend" / "streamlit_app.py"


def test_streamlit_app_parses():
    ast.parse(STREAMLIT_APP.read_text(encoding="utf-8"), filename=str(STREAMLIT_APP))


def test_streamlit_api_helper_calls_are_defined():
    tree = ast.parse(STREAMLIT_APP.read_text(encoding="utf-8"), filename=str(STREAMLIT_APP))
    defined_helpers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("api_")
    }
    called_helpers = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("api_")
    }

    assert called_helpers - defined_helpers == set()


def _load_streamlit_namespace():
    tree = ast.parse(STREAMLIT_APP.read_text(encoding="utf-8"), filename=str(STREAMLIT_APP))
    safe_defs = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
    module = ast.fix_missing_locations(ast.Module(body=safe_defs, type_ignores=[]))
    namespace = {}
    exec(compile(module, filename=str(STREAMLIT_APP), mode="exec"), namespace)
    return namespace


def _load_streamlit_function(function_name: str):
    return _load_streamlit_namespace()[function_name]


def test_url_ingest_payload_omits_missing_or_placeholder_source_id():
    build_payload = _load_streamlit_function("build_url_ingest_payload")

    base_payload = {
        "url": "https://example.org/article",
        "topic_tags": "diplomacy",
        "sensitivity_level": "medium",
        "language": "English",
    }

    assert "source_id" not in build_payload(**base_payload, source_id=None)
    assert "source_id" not in build_payload(**base_payload, source_id=0)
    assert build_payload(**base_payload, source_id=7)["source_id"] == 7


def test_source_create_payload_normalizes_name_and_trims_optional_fields():
    build_payload = _load_streamlit_function("build_source_create_payload")

    payload = build_payload(
        name="  European   Commission - AI  ",
        base_url=" https://digital-strategy.ec.europa.eu/ ",
        source_type="official",
        reliability_tier="high",
        country_or_institution=" EU ",
        notes=" Official EU digital policy source. ",
        is_active=True,
    )

    assert payload["name"] == "European Commission - AI"
    assert payload["base_url"] == "https://digital-strategy.ec.europa.eu/"
    assert payload["country_or_institution"] == "EU"
    assert payload["notes"] == "Official EU digital policy source."


def test_frontend_reuses_existing_source_by_normalized_name():
    namespace = _load_streamlit_namespace()
    find_source = namespace["find_source_by_name"]
    sources = [{"id": 12, "name": "European Commission - AI"}]

    source = find_source(sources, "  European   Commission - AI  ")

    assert source["id"] == 12


def test_url_ingest_source_labels_distinguish_empty_selection_from_real_ids():
    source = STREAMLIT_APP.read_text(encoding="utf-8")

    assert 'NO_SOURCE_SELECTED_LABEL = "No source selected"' in source
    assert "Source ID {s['id']}:" in source


def sample_event(**overrides):
    event = {
        "id": 1,
        "title": "NIST publishes AI RMF update",
        "summary": "NIST published an update relevant to AI governance.",
        "event_type": "development",
        "status": "active",
        "primary_language": "English",
        "country_or_region": "US",
        "first_seen_at": "2026-07-01T09:00:00",
        "last_seen_at": "2026-07-02T10:00:00",
        "created_at": "2026-07-01T09:00:00",
        "updated_at": "2026-07-02T10:00:00",
        "related_document_count": 1,
        "distinct_source_count": 1,
        "distinct_publisher_count": 1,
    }
    event.update(overrides)
    return event


def sample_document(**overrides):
    document = {
        "event_id": 1,
        "document_id": 10,
        "document_title": "NIST AI RMF article",
        "source_name": "NIST",
        "publisher": "NIST",
        "url": "https://nist.gov/article",
        "published_date": "2026-07-01",
        "fetched_at": "2026-07-02T10:00:00",
        "relationship_type": "primary",
        "similarity_score": 1,
        "clustering_method": "new_event",
    }
    document.update(overrides)
    return document


def sample_snapshot(**overrides):
    snapshot = {
        "id": 1,
        "event_id": 1,
        "snapshot_type": "baseline",
        "event_title": "NIST publishes AI RMF update",
        "event_status": "active",
        "event_type": "development",
        "document_count": 1,
        "distinct_source_count": 1,
        "distinct_publisher_count": 1,
        "document_ids": [10],
        "source_names": ["NIST"],
        "publisher_names": ["NIST"],
        "evidence_items": [sample_document()],
        "latest_evidence_at": "2026-07-02T10:00:00",
        "snapshot_hash": "abc123",
        "created_at": "2026-07-02T11:00:00",
    }
    snapshot.update(overrides)
    return snapshot


def sample_change(**overrides):
    change = {
        "has_changes": False,
        "change_level": "none",
        "is_initial_baseline": True,
        "new_document_ids": [],
        "removed_document_ids": [],
        "new_sources": [],
        "removed_sources": [],
        "new_publishers": [],
        "removed_publishers": [],
        "document_count_delta": 0,
        "source_count_delta": 0,
        "publisher_count_delta": 0,
        "metadata_changes": {},
        "latest_evidence_at_changed": False,
        "summary_changed": False,
        "deterministic_change_summary": "Initial event baseline - no previous snapshot is available for comparison.",
    }
    change.update(overrides)
    return change


def sample_brief(**overrides):
    brief = {
        "id": 5,
        "event_id": 1,
        "snapshot_id": 1,
        "previous_snapshot_id": None,
        "brief_status": "draft",
        "headline": "NIST publishes AI RMF update",
        "what_happened": "The event is represented by one document.",
        "what_changed": "Initial event baseline - no previous snapshot is available for comparison.",
        "why_it_matters": "Review source coverage before external use.",
        "confirmed_points": ["Snapshot contains 1 evidence document."],
        "uncertainties": ["No previous snapshot is available."],
        "watch_next": ["Monitor new evidence."],
        "evidence_document_ids": [10],
        "evidence_items": [sample_document()],
        "change_summary": sample_change(),
        "generation_method": "deterministic",
        "created_at": "2026-07-02T11:05:00",
        "updated_at": "2026-07-02T11:05:00",
    }
    brief.update(overrides)
    return brief


def test_event_list_response_parsing_handles_optional_metadata():
    parse_events = _load_streamlit_function("parse_event_list_response")

    events = parse_events(
        [
            sample_event(),
            {
                "id": 2,
                "title": "Untyped event",
                "first_seen_at": "2026-07-01T00:00:00",
                "last_seen_at": "2026-07-01T00:00:00",
            },
        ]
    )

    assert events[0]["related_document_count"] == 1
    assert events[1]["summary"] == ""
    assert events[1]["event_type"] == ""


def test_event_detail_and_documents_response_parsing():
    namespace = _load_streamlit_namespace()
    parse_detail = namespace["parse_event_detail_response"]
    parse_documents = namespace["parse_event_documents_response"]

    detail = parse_detail({**sample_event(), "related_documents": [sample_document()]})
    documents = parse_documents([sample_document(document_id=11, publisher=None)])

    assert detail["related_documents"][0]["document_title"] == "NIST AI RMF article"
    assert documents[0]["publisher"] == ""


def test_event_intelligence_response_parsing():
    namespace = _load_streamlit_namespace()

    snapshot = namespace["parse_event_snapshot_response"](sample_snapshot())
    snapshots = namespace["parse_event_snapshots_response"]([sample_snapshot(id=2)])
    change = namespace["normalize_event_change_payload"](sample_change())
    brief = namespace["parse_event_brief_response"](sample_brief())
    briefs = namespace["parse_event_briefs_response"]([sample_brief(id=6)])
    created = namespace["parse_event_snapshot_create_response"](
        {"status": "ok", "reused": False, "snapshot": sample_snapshot()}
    )
    generated = namespace["parse_event_brief_generate_response"](
        {"status": "ok", "reused": False, "brief": sample_brief(), "change": sample_change()}
    )

    assert snapshot["document_count"] == 1
    assert snapshots[0]["id"] == 2
    assert change["is_initial_baseline"] is True
    assert change["has_changes"] is False
    assert change["change_level"] == "none"
    assert brief["generation_method"] == "deterministic"
    assert briefs[0]["id"] == 6
    assert created["snapshot"]["id"] == 1
    assert generated["brief"]["id"] == 5


def test_snapshot_history_change_level():
    change_level = _load_streamlit_function("snapshot_history_change_level")
    baseline = sample_snapshot()
    same = sample_snapshot(id=2)
    minor = sample_snapshot(id=3, snapshot_hash="def456", document_ids=[10, 11])
    meaningful = sample_snapshot(
        id=4,
        snapshot_hash="ghi789",
        document_ids=[10, 11, 12],
        publisher_names=["NIST", "OECD"],
    )

    assert change_level(None, baseline) == "baseline"
    assert change_level(baseline, same) == "none"
    assert change_level(baseline, minor) == "minor"
    assert change_level(minor, meaningful) == "meaningful"


def test_empty_event_list_and_filtered_empty_result():
    namespace = _load_streamlit_namespace()

    assert namespace["parse_event_list_response"]([]) == []
    assert namespace["filter_events"]([sample_event()], text_query="missing") == []


def test_event_filters_cover_status_type_language_region_documents_and_sources():
    filter_events = _load_streamlit_function("filter_events")
    events = [
        sample_event(id=1, status="active", event_type="development", primary_language="English", country_or_region="US", related_document_count=3, distinct_publisher_count=2),
        sample_event(id=2, title="EU AI Act", summary="EU implementation update.", status="archived", event_type="reaction", primary_language="French", country_or_region="EU", related_document_count=1, distinct_publisher_count=1),
    ]

    assert [e["id"] for e in filter_events(events, text_query="NIST")] == [1]
    assert [e["id"] for e in filter_events(events, statuses=["active"])] == [1]
    assert [e["id"] for e in filter_events(events, event_types=["reaction"])] == [2]
    assert [e["id"] for e in filter_events(events, languages=["English"])] == [1]
    assert [e["id"] for e in filter_events(events, countries=["EU"])] == [2]
    assert [e["id"] for e in filter_events(events, min_documents=2)] == [1]
    assert [e["id"] for e in filter_events(events, multi_source_only=True)] == [1]


def test_event_sorting_options_are_deterministic_with_missing_dates():
    sort_events = _load_streamlit_function("sort_events")
    events = [
        sample_event(id=1, title="Bravo", first_seen_at=None, last_seen_at=None, related_document_count=1, distinct_publisher_count=1),
        sample_event(id=2, title="Alpha", first_seen_at="2026-07-01T00:00:00", last_seen_at="2026-07-03T00:00:00", related_document_count=5, distinct_publisher_count=2),
        sample_event(id=3, title="Charlie", first_seen_at="2026-07-02T00:00:00", last_seen_at="2026-07-02T00:00:00", related_document_count=2, distinct_publisher_count=4),
    ]

    assert [e["id"] for e in sort_events(events, "Newest activity")] == [2, 3, 1]
    assert [e["id"] for e in sort_events(events, "First seen")] == [3, 2, 1]
    assert [e["id"] for e in sort_events(events, "Document count")] == [2, 3, 1]
    assert [e["id"] for e in sort_events(events, "Source or publisher count")] == [3, 2, 1]
    assert [e["id"] for e in sort_events(events, "Title")] == [2, 1, 3]


def test_event_document_counts_and_publisher_deduplication():
    namespace = _load_streamlit_namespace()
    count_publishers = namespace["distinct_publisher_count"]
    metrics = namespace["event_overview_metrics"]

    documents = [
        sample_document(document_id=1, publisher="NIST", source_name="NIST"),
        sample_document(document_id=2, publisher="NIST", source_name="NIST"),
        sample_document(document_id=3, publisher="OECD", source_name="OECD"),
    ]
    events = [
        sample_event(related_document_count=1, distinct_publisher_count=1),
        sample_event(id=2, related_document_count=3, distinct_publisher_count=2),
    ]

    assert count_publishers(documents) == 2
    assert metrics(events, now=__import__("datetime").datetime(2026, 7, 3))["total_documents"] == 4
    assert metrics(events, now=__import__("datetime").datetime(2026, 7, 3))["multi_source_events"] == 1


def test_timeline_ordering_uses_publication_date_then_fetched_date():
    timeline_documents = _load_streamlit_function("timeline_documents")
    documents = [
        sample_document(document_id=1, published_date=None, fetched_at="2026-07-03T12:00:00"),
        sample_document(document_id=2, published_date="2026-07-01", fetched_at="2026-07-04T12:00:00"),
        sample_document(document_id=3, published_date=None, fetched_at="2026-07-02T12:00:00"),
    ]

    assert [doc["document_id"] for doc in timeline_documents(documents)] == [2, 3, 1]


def test_date_similarity_and_clustering_formatting():
    namespace = _load_streamlit_namespace()

    assert namespace["format_date_value"]("2026-07-02") == "Jul 2, 2026"
    assert namespace["format_datetime_value"]("2026-07-02T09:15:00") == "Jul 2, 2026 09:15"
    assert namespace["format_date_value"]("not-a-date") == "Not available"
    assert namespace["format_similarity_score"](1) == "100%"
    assert namespace["format_similarity_score"](0.92345678) == "92.3%"
    assert namespace["clustering_method_label"]("new_event") == "Created as a new event"
    assert namespace["clustering_method_label"]("normalized_url") == "Matched by normalized URL"
    assert namespace["clustering_method_label"]("unseen_method") == "Unknown method (unseen method)"
    assert namespace["format_signed_delta"](2, "document") == "+2 documents"
    assert namespace["format_signed_delta"](-1, "source") == "-1 source"


def test_malformed_api_response_and_concise_errors():
    namespace = _load_streamlit_namespace()
    parse_events = namespace["parse_event_list_response"]
    error_class = namespace["FrontendAPIError"]

    try:
        parse_events({"events": []})
    except error_class as exc:
        assert str(exc) == "Event list response was malformed."
    else:
        raise AssertionError("Malformed response should raise FrontendAPIError")

    assert namespace["_concise_error"]("Traceback SELECT * FROM documents", "Request failed.") == "Request failed."
    assert namespace["_concise_error"]("psycopg.DataError %PDF-1.7 parameters: binary", "Request failed.") == "Request failed."


def test_api_helper_handles_backend_unavailable_timeout_and_malformed_json():
    namespace = _load_streamlit_namespace()
    error_class = namespace["FrontendAPIError"]

    class Timeout(Exception):
        pass

    class ConnectionError(Exception):
        pass

    class RequestException(Exception):
        pass

    FakeExceptions = type(
        "FakeExceptions",
        (),
        {
            "Timeout": Timeout,
            "ConnectionError": ConnectionError,
            "RequestException": RequestException,
        },
    )

    class FakeRequests:
        exceptions = FakeExceptions
        mode = "connection"

        @classmethod
        def request(cls, *args, **kwargs):
            if cls.mode == "timeout":
                raise Timeout("slow")
            if cls.mode == "connection":
                raise ConnectionError("refused")
            return FakeResponse()

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("bad json")

    namespace["requests"] = FakeRequests
    namespace["API_BASE_URL"] = "http://backend.test"

    for mode, expected in [
        ("connection", "Backend is not reachable"),
        ("timeout", "Request timed out"),
        ("malformed", "Backend returned malformed JSON."),
    ]:
        FakeRequests.mode = mode
        try:
            namespace["api_get"]("/events")
        except error_class as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("API failure should raise FrontendAPIError")


def test_existing_pages_and_events_navigation_are_present():
    source = STREAMLIT_APP.read_text(encoding="utf-8")
    for page_name in [
        "Start Here",
        "Dashboard",
        "Events",
        "Ingest URL",
        "Documents",
        "Semantic Search",
        "Ask Knowledge Base",
        "Generate Brief",
        "Review Briefs",
        "Export Brief",
        "Audit Logs",
        "Governance",
    ]:
        assert f'"{page_name}"' in source
        assert f'page == "{page_name}"' in source or page_name == "Start Here"


def test_no_mixed_language_labels_or_placeholder_images_added():
    source = STREAMLIT_APP.read_text(encoding="utf-8")

    assert "Search title or summary" in source
    assert "Supporting documents and evidence" in source
    assert "Event Intelligence" in source
    for serbian_word in ["Dokumenti", "Pretraga", "Izvori", "Događaji", "Dogadjaji"]:
        assert serbian_word not in source
    for placeholder in ["placeholder.com", "placehold.co", "loremflickr", "unsplash"]:
        assert placeholder not in source


def test_reclustering_runs_only_after_explicit_button_interaction():
    source = STREAMLIT_APP.read_text(encoding="utf-8")

    assert 'if st.button("Recluster selected document")' in source
    assert "result = recluster_document(recluster_document_id)" in source


def test_event_intelligence_actions_are_explicit_and_cache_clearing_is_present():
    source = STREAMLIT_APP.read_text(encoding="utf-8")

    assert 'if st.button("Create snapshot")' in source
    assert 'if st.button("Generate event brief")' in source
    assert 'if st.button("Refresh intelligence")' in source
    assert "create_event_snapshot(selected_event_id)" in source
    assert "generate_event_brief(selected_event_id)" in source
    assert "clear_event_cache(selected_event_id)" in source


def test_event_intelligence_wording_history_and_evidence_links_are_present():
    source = STREAMLIT_APP.read_text(encoding="utf-8")

    assert "Initial event baseline - no previous snapshot is available for comparison." in source
    assert "No meaningful change detected since the previous snapshot." in source
    assert "Snapshot and brief history" in source
    assert "Latest Event Brief" in source
    assert "Evidence links" in source
    assert "No event snapshot exists yet." in source
