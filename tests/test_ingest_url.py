import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pypdf import PdfWriter

from app.api.routes.ingest import ingest_public_url
from app.api.routes.sources import create_source
from app.models import AuditLog, Document, Event, EventDocument, Source
from app.schemas.ingest import UrlIngestRequest
from app.schemas.source import SourceCreate
from app.services.ingestion import (
    ExtractedArticle,
    IngestionError,
    detect_content_type,
    extract_article_from_pdf,
    extract_pdf_title,
    is_pdf_response,
    sanitize_text,
)


@pytest.fixture()
def ingest_db_session(tmp_path):
    database_path = tmp_path / "ingest.db"
    engine = create_engine(f"sqlite:///{database_path}")

    Source.__table__.create(bind=engine)
    Document.__table__.create(bind=engine)
    Event.__table__.create(bind=engine)
    EventDocument.__table__.create(bind=engine)
    AuditLog.__table__.create(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def extracted_article(monkeypatch):
    def stub_extract_article_from_url(url: str) -> ExtractedArticle:
        return ExtractedArticle(
            title="Stubbed policy article",
            raw_text="Raw evidence text. " * 20,
            cleaned_text="Clean evidence text. " * 20,
        )

    monkeypatch.setattr(
        "app.services.ingestion.extract_article_from_url",
        stub_extract_article_from_url,
    )


class FakeResponse:
    def __init__(self, content: bytes, *, content_type: str = "application/pdf", status_code: int = 200):
        self.content = content
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(content)),
        }
        self.status_code = status_code

    def iter_content(self, chunk_size=65536):
        for idx in range(0, len(self.content), chunk_size):
            yield self.content[idx : idx + chunk_size]


def make_text_pdf(text: str, *, metadata_title: str | None = None, pages: int = 1) -> bytes:
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    page_streams = [
        f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("latin1", errors="ignore")
        for _ in range(pages)
    ]
    objects = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add(b"<< /Type /Catalog /Pages 2 0 R" + (b" /Metadata 0 0 R" if False else b"") + b" >>")
    pages_id = add(b"")
    page_ids = []
    font_id = None
    content_ids = []
    for stream in page_streams:
        content_ids.append(add(b"<< /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream"))
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for content_id in content_ids:
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/MediaBox [0 0 612 792] /Contents {content_id} 0 R >>".encode()
            )
        )
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] "
        f"/Count {len(page_ids)} >>"
    ).encode()
    info_id = None
    if metadata_title:
        escaped_title = metadata_title.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        info_id = add(f"<< /Title ({escaped_title}) /CreationDate (D:20260612093000Z) >>".encode("latin1", "ignore"))

    output = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{index} 0 obj ".encode() + obj + b" endobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer << /Size {len(objects) + 1} /Root {catalog_id} 0 R"
    if info_id:
        trailer += f" /Info {info_id} 0 R"
    trailer += f" >>\nstartxref\n{xref}\n%%EOF\n"
    output += trailer.encode()
    return output


def make_unicode_pdf(text: str) -> bytes:
    chars = []
    for char in text:
        if char not in chars:
            chars.append(char)
    mapping = {char: f"{idx:04X}" for idx, char in enumerate(chars, start=1)}
    entries = [
        f"<{mapping[char]}> <{char.encode('utf-16-be').hex().upper()}>"
        for char in chars
    ]
    encoded_text = "".join(mapping[char] for char in text)
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Test def\n/CMapType 2 def\n1 begincodespacerange\n<0000> <FFFF>\n"
        f"endcodespacerange\n{len(entries)} beginbfchar\n"
        + "\n".join(entries)
        + "\nendbfchar\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode("ascii")
    stream = f"BT /F1 12 Tf 72 720 Td <{encoded_text}> Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 8 0 R >>",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /TestFont /Encoding /Identity-H /DescendantFonts [5 0 R] /ToUnicode 7 0 R >>",
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /TestFont /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 6 0 R >>",
        b"<< /Type /FontDescriptor /FontName /TestFont /Flags 4 /FontBBox [0 -1000 1000 1000] /ItalicAngle 0 /Ascent 1000 /Descent -200 /CapHeight 700 /StemV 80 >>",
        b"<< /Length " + str(len(cmap)).encode() + b" >> stream\n" + cmap + b"\nendstream",
        b"<< /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream",
    ]
    output = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{index} 0 obj ".encode() + obj + b" endobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return output


def make_blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    import io

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    import io

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_ingest_url_without_source_id(ingest_db_session, extracted_article):
    payload = UrlIngestRequest(
        url="https://example.org/no-source",
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    response = ingest_public_url(payload, ingest_db_session)

    document = ingest_db_session.get(Document, response.document_id)
    assert response.status == "ok"
    assert document.source_id is None
    assert document.url == "https://example.org/no-source"
    assert ingest_db_session.query(EventDocument).filter_by(document_id=document.id).count() == 1


def test_ingest_url_with_valid_source_id(ingest_db_session, extracted_article):
    source = Source(
        name="Example Ministry",
        base_url="https://example.org",
        source_type="government",
        reliability_tier="high",
    )
    ingest_db_session.add(source)
    ingest_db_session.commit()
    ingest_db_session.refresh(source)

    payload = UrlIngestRequest(
        url="https://example.org/valid-source",
        source_id=source.id,
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    response = ingest_public_url(payload, ingest_db_session)

    document = ingest_db_session.get(Document, response.document_id)
    assert response.status == "ok"
    assert document.source_id == source.id
    assert ingest_db_session.query(EventDocument).filter_by(document_id=document.id).count() == 1


def test_ingest_url_with_invalid_source_id_returns_400(ingest_db_session, monkeypatch):
    def fail_if_article_extraction_runs(url: str) -> ExtractedArticle:
        raise AssertionError("Article extraction should not run for invalid source_id")

    monkeypatch.setattr(
        "app.services.ingestion.extract_article_from_url",
        fail_if_article_extraction_runs,
    )
    payload = UrlIngestRequest(
        url="https://example.org/invalid-source",
        source_id=999,
        topic_tags="diplomacy",
        sensitivity_level="medium",
        language="English",
    )

    with pytest.raises(HTTPException) as exc_info:
        ingest_public_url(payload, ingest_db_session)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Source with id=999 does not exist."


def test_url_ingestion_with_existing_source(ingest_db_session, extracted_article):
    source = Source(
        name="Existing Source",
        base_url="https://example.org",
        source_type="official",
        reliability_tier="high",
    )
    ingest_db_session.add(source)
    ingest_db_session.commit()
    ingest_db_session.refresh(source)

    response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/existing-source-ingest",
            source_id=source.id,
            topic_tags="diplomacy",
            sensitivity_level="medium",
            language="English",
        ),
        ingest_db_session,
    )

    document = ingest_db_session.get(Document, response.document_id)
    assert document.source_id == source.id


def test_url_ingestion_with_newly_created_source(ingest_db_session, extracted_article):
    source = create_source(
        SourceCreate(
            name="  Newly Created Source  ",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )

    response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/newly-created-source-ingest",
            source_id=source.id,
            topic_tags="diplomacy",
            sensitivity_level="medium",
            language="English",
        ),
        ingest_db_session,
    )

    document = ingest_db_session.get(Document, response.document_id)
    assert source.name == "Newly Created Source"
    assert document.source_id == source.id


def test_url_ingestion_repeated_source_creation_reuses_same_source(
    ingest_db_session,
    extracted_article,
):
    first_source = create_source(
        SourceCreate(
            name="Repeated Source",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )
    second_source = create_source(
        SourceCreate(
            name="  Repeated Source  ",
            base_url="https://example.org",
            source_type="official",
            reliability_tier="high",
        ),
        response=Response(),
        db=ingest_db_session,
    )

    first_response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/repeated-source-ingest-1",
            source_id=first_source.id,
        ),
        ingest_db_session,
    )
    second_response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/repeated-source-ingest-2",
            source_id=second_source.id,
        ),
        ingest_db_session,
    )

    first_document = ingest_db_session.get(Document, first_response.document_id)
    second_document = ingest_db_session.get(Document, second_response.document_id)
    assert second_source.id == first_source.id
    assert ingest_db_session.query(Source).count() == 1
    assert first_document.source_id == first_source.id
    assert second_document.source_id == first_source.id


def test_url_ingest_request_rejects_placeholder_source_id_zero():
    with pytest.raises(ValidationError):
        UrlIngestRequest(
            url="https://example.org/placeholder-source",
            source_id=0,
        )


def test_pdf_detection_by_content_type_magic_octet_stream_and_suffix():
    pdf = b"%PDF-1.7\ncontent"
    html = b"<html><body>Not a PDF</body></html>"

    assert detect_content_type("application/pdf; charset=binary") == "application/pdf"
    assert is_pdf_response(content_type="application/pdf; charset=binary", body=html, url="https://example.org/file") is True
    assert is_pdf_response(content_type="application/octet-stream", body=pdf, url="https://example.org/file") is True
    assert is_pdf_response(content_type="text/plain", body=pdf, url="https://example.org/file") is True
    assert is_pdf_response(content_type="", body=b"unknown", url="https://example.org/file.pdf") is True
    assert is_pdf_response(content_type="text/html", body=html, url="https://example.org/file.pdf") is False


def test_pdf_text_extraction_metadata_title_and_date():
    pdf = make_text_pdf(
        "Policy PDF Heading\nThis is a text-based policy document. " * 20,
        metadata_title="Useful PDF Metadata Title",
    )

    article = extract_article_from_pdf("https://example.org/policy.pdf", pdf)

    assert article.title == "Useful PDF Metadata Title"
    assert "text-based policy document" in article.cleaned_text
    assert article.published_date.isoformat() == "2026-06-12"
    assert "%PDF" not in article.raw_text
    assert "\x00" not in article.raw_text


def test_pdf_multi_page_and_japanese_unicode_extraction():
    english_pdf = make_text_pdf("First page policy text. " * 20, pages=2)
    japanese_text = "デジタル庁 AI ガバナンス指針。これは日本語の政策文書です。" * 5
    japanese_pdf = make_unicode_pdf(japanese_text)

    english_article = extract_article_from_pdf("https://example.org/multipage.pdf", english_pdf)
    japanese_article = extract_article_from_pdf("https://example.org/japanese.pdf", japanese_pdf)

    assert english_article.cleaned_text.count("First page policy text") >= 2
    assert "デジタル庁" in japanese_article.cleaned_text
    assert "日本語の政策文書" in japanese_article.cleaned_text


def test_pdf_title_fallbacks_reject_generic_metadata_and_use_filename():
    text = "Meaningful Government Guidance Heading\n" + ("Policy text. " * 30)

    assert extract_pdf_title(
        url="https://example.org/files/raw_document.pdf",
        metadata_title="Untitled",
        text=text,
    ) == "Meaningful Government Guidance Heading"
    assert extract_pdf_title(
        url="https://example.org/files/cabinet_office_ai_guideline_2026.pdf",
        metadata_title="Untitled",
        text="",
    ) == "cabinet office ai guideline 2026"


def test_text_sanitation_removes_nul_and_controls_preserving_japanese_and_newlines():
    dirty = "Line 1\x00\nデジタル庁\tAI\x01\x02 café"

    sanitized = sanitize_text(dirty)

    assert "\x00" not in sanitized
    assert "\x01" not in sanitized
    assert "\n" in sanitized
    assert "\t" in sanitized
    assert "デジタル庁" in sanitized
    assert "café" in sanitized


def test_pdf_failures_for_image_only_malformed_truncated_and_encrypted():
    with pytest.raises(IngestionError, match="OCR is not supported"):
        extract_article_from_pdf("https://example.org/blank.pdf", make_blank_pdf())

    for payload in [b"%PDF-1.7\nbroken", b"%PDF-1.7\n1 0 obj <<"]:
        with pytest.raises(IngestionError):
            extract_article_from_pdf("https://example.org/malformed.pdf", payload)

    with pytest.raises(IngestionError, match="encrypted|password"):
        extract_article_from_pdf("https://example.org/encrypted.pdf", make_encrypted_pdf())


def test_successful_pdf_ingestion_creates_document_and_primary_event(ingest_db_session, monkeypatch):
    pdf = make_text_pdf("Government AI policy guidance direct PDF. " * 20, metadata_title="Government AI PDF")

    def fake_get(*args, **kwargs):
        return FakeResponse(pdf, content_type="application/pdf")

    monkeypatch.setattr("app.services.ingestion.requests.get", fake_get)

    response = ingest_public_url(
        UrlIngestRequest(
            url="https://example.org/government-ai.pdf",
            topic_tags="AI governance",
            sensitivity_level="medium",
            language="Japanese",
        ),
        ingest_db_session,
    )

    document = ingest_db_session.get(Document, response.document_id)
    assert response.status == "ok"
    assert document.title == "Government AI PDF"
    assert document.language == "Japanese"
    assert "Government AI policy guidance" in document.cleaned_text
    assert "\x00" not in document.cleaned_text
    assert ingest_db_session.query(Document).count() == 1
    assert ingest_db_session.query(EventDocument).filter_by(document_id=document.id).count() == 1


def test_failed_pdf_ingestion_creates_no_records(ingest_db_session, monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(make_blank_pdf(), content_type="application/pdf")

    monkeypatch.setattr("app.services.ingestion.requests.get", fake_get)

    with pytest.raises(HTTPException) as exc_info:
        ingest_public_url(UrlIngestRequest(url="https://example.org/scanned.pdf"), ingest_db_session)

    assert exc_info.value.status_code == 422
    assert "OCR is not supported" in exc_info.value.detail
    assert ingest_db_session.query(Document).count() == 0
    assert ingest_db_session.query(Event).count() == 0
    assert ingest_db_session.query(EventDocument).count() == 0


def test_pdf_duplicate_url_and_identical_content_event_clustering(ingest_db_session, monkeypatch):
    pdf = make_text_pdf("Repeated PDF content for event clustering. " * 20, metadata_title="Repeated PDF")

    def fake_get(*args, **kwargs):
        return FakeResponse(pdf, content_type="application/pdf")

    monkeypatch.setattr("app.services.ingestion.requests.get", fake_get)
    first = ingest_public_url(UrlIngestRequest(url="https://example.org/repeated.pdf"), ingest_db_session)
    with pytest.raises(HTTPException) as exc_info:
        ingest_public_url(UrlIngestRequest(url="https://example.org/repeated.pdf"), ingest_db_session)
    second = ingest_public_url(
        UrlIngestRequest(url="https://example.org/repeated.pdf?utm_source=newsletter"),
        ingest_db_session,
    )
    third = ingest_public_url(
        UrlIngestRequest(url="https://mirror.example.org/repeated-copy.pdf"),
        ingest_db_session,
    )

    first_link = ingest_db_session.query(EventDocument).filter_by(document_id=first.document_id).one()
    second_link = ingest_db_session.query(EventDocument).filter_by(document_id=second.document_id).one()
    third_link = ingest_db_session.query(EventDocument).filter_by(document_id=third.document_id).one()

    assert exc_info.value.status_code == 400
    assert "already exists" in exc_info.value.detail
    assert second_link.event_id == first_link.event_id
    assert second_link.clustering_method == "normalized_url"
    assert third_link.event_id == first_link.event_id
    assert third_link.clustering_method == "content_hash"


def test_download_failures_are_concise_and_do_not_expose_sql_or_binary(ingest_db_session, monkeypatch):
    def timeout_get(*args, **kwargs):
        import requests

        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr("app.services.ingestion.requests.get", timeout_get)
    with pytest.raises(HTTPException) as timeout_exc:
        ingest_public_url(UrlIngestRequest(url="https://example.org/timeout.pdf"), ingest_db_session)

    assert timeout_exc.value.status_code == 408
    assert "timed out" in timeout_exc.value.detail.lower()

    def bad_status_get(*args, **kwargs):
        return FakeResponse(b"not found", content_type="text/plain", status_code=404)

    monkeypatch.setattr("app.services.ingestion.requests.get", bad_status_get)
    with pytest.raises(HTTPException) as status_exc:
        ingest_public_url(UrlIngestRequest(url="https://example.org/not-found.pdf"), ingest_db_session)

    assert status_exc.value.status_code == 400
    assert "HTTP status 404" in status_exc.value.detail
    assert "%PDF" not in status_exc.value.detail
    assert "INSERT INTO" not in status_exc.value.detail
    assert len(status_exc.value.detail) <= 240


def test_oversized_and_unsupported_content_type_fail_cleanly(ingest_db_session, monkeypatch):
    def oversized_get(*args, **kwargs):
        response = FakeResponse(b"x", content_type="application/pdf")
        response.headers["content-length"] = str(100_000_000)
        return response

    monkeypatch.setattr("app.services.ingestion.requests.get", oversized_get)
    with pytest.raises(HTTPException) as oversized_exc:
        ingest_public_url(UrlIngestRequest(url="https://example.org/large.pdf"), ingest_db_session)
    assert oversized_exc.value.status_code == 413

    def json_get(*args, **kwargs):
        return FakeResponse(b'{"status":"ok"}', content_type="application/json")

    monkeypatch.setattr("app.services.ingestion.requests.get", json_get)
    with pytest.raises(HTTPException) as unsupported_exc:
        ingest_public_url(UrlIngestRequest(url="https://example.org/data"), ingest_db_session)
    assert unsupported_exc.value.status_code == 415


def test_html_ingestion_sanitizes_text_without_damaging_japanese(ingest_db_session, monkeypatch):
    html = """
    <html><head><title>Japanese HTML Policy</title></head>
    <body><h1>デジタル政策</h1><p>English and 日本語 text about AI governance.</p>
    <p>More policy content for extraction. </p></body></html>
    """ + ("<p>追加の政策本文です。English policy context for reliable extraction.</p>" * 60)

    def fake_get(*args, **kwargs):
        return FakeResponse(html.encode("utf-8"), content_type="text/html; charset=utf-8")

    monkeypatch.setattr("app.services.ingestion.requests.get", fake_get)

    response = ingest_public_url(
        UrlIngestRequest(url="https://example.org/html", language="Japanese"),
        ingest_db_session,
    )
    document = ingest_db_session.get(Document, response.document_id)

    assert document.title in {"Japanese HTML Policy", "デジタル政策"}
    assert "デジタル政策" in document.cleaned_text
    assert "English" in document.cleaned_text
    assert "\x00" not in document.cleaned_text
    assert ingest_db_session.query(EventDocument).filter_by(document_id=document.id).count() == 1


def test_generic_api_error_is_sanitized(ingest_db_session, monkeypatch):
    def fail_ingest(*args, **kwargs):
        raise RuntimeError("SQLAlchemy INSERT INTO documents VALUES (%PDF-1.7 binary)")

    monkeypatch.setattr("app.api.routes.ingest.ingest_url", fail_ingest)

    with pytest.raises(HTTPException) as exc_info:
        ingest_public_url(UrlIngestRequest(url="https://example.org/failure.pdf"), ingest_db_session)

    assert exc_info.value.status_code == 500
    assert "INSERT INTO" not in exc_info.value.detail
    assert "%PDF" not in exc_info.value.detail
    assert "binary" not in exc_info.value.detail
    assert len(exc_info.value.detail) <= 240
