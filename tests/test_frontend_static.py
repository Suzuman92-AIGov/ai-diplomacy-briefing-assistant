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
    function_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    module = ast.fix_missing_locations(ast.Module(body=function_defs, type_ignores=[]))
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
