from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.source import Source
from app.services.audit import create_audit_log
from app.services.events import assign_document_to_event


@dataclass
class ExtractedArticle:
    title: str
    raw_text: str
    cleaned_text: str
    published_date: date | None = None


@dataclass
class DownloadedContent:
    url: str
    content: bytes
    content_type: str


class IngestionError(Exception):
    status_code = 400

    def __init__(self, public_message: str, *, status_code: int | None = None):
        super().__init__(public_message)
        self.public_message = sanitize_error_message(public_message)
        if status_code is not None:
            self.status_code = status_code


class DuplicateDocumentError(IngestionError):
    status_code = 400


class UnsupportedContentTypeError(IngestionError):
    status_code = 415


class PDFNoExtractableTextError(IngestionError):
    status_code = 422


class PDFParseError(IngestionError):
    status_code = 422


class OversizedDownloadError(IngestionError):
    status_code = 413


class DownloadError(IngestionError):
    status_code = 400


ALLOWED_CONTROL_CHARS = {"\n", "\r", "\t"}
GENERIC_PDF_TITLES = {
    "",
    "untitled",
    "unknown",
    "document",
    "microsoft word",
    "microsoft powerpoint",
    "powerpoint presentation",
    "pages",
}
HTML_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
}
TEXT_LIKE_CONTENT_TYPES = {
    "text/plain",
    "application/xml",
    "text/xml",
}


def sanitize_text(value: str | None, *, max_chars: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    sanitized = []
    for char in text.replace("\x00", ""):
        codepoint = ord(char)
        if char in ALLOWED_CONTROL_CHARS or codepoint >= 32:
            sanitized.append(char)
    result = "".join(sanitized).replace("\r\n", "\n").replace("\r", "\n").strip()
    if max_chars is not None:
        result = result[:max_chars]
    return result


def sanitize_error_message(message: str | None) -> str:
    text = sanitize_text(message or "Request failed.") or "Request failed."
    sensitive_markers = [
        "traceback",
        "sqlalchemy",
        "psycopg",
        "postgresql",
        "insert into",
        "select ",
        "parameters:",
        "%pdf-",
    ]
    lowered = text.lower()
    if any(marker in lowered for marker in sensitive_markers):
        text = "Ingestion failed. The document could not be saved safely."
    return " ".join(text.split())[: settings.ingestion_error_max_chars]


def _fallback_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = unquote(parsed.path.strip("/")).replace("-", " ").replace("_", " ")
    if path:
        return sanitize_title(path[:120]) or "Untitled document"
    return parsed.netloc or "Untitled document"


def _clean_text(text: str) -> str:
    text = sanitize_text(text, max_chars=settings.ingestion_max_extracted_text_chars) or ""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines)


def sanitize_title(value: str | None) -> str | None:
    title = sanitize_text(value, max_chars=500)
    if not title:
        return None
    title = " ".join(title.split())
    return title[:500] or None


def detect_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _looks_like_pdf(body: bytes) -> bool:
    return body.lstrip().startswith(b"%PDF-")


def _looks_like_html(body: bytes) -> bool:
    prefix = body[:512].lower().lstrip()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<html" in prefix[:120]


def is_pdf_response(*, content_type: str | None, body: bytes, url: str) -> bool:
    normalized_type = detect_content_type(content_type)
    if normalized_type == "application/pdf":
        return True
    if _looks_like_pdf(body):
        return True
    if normalized_type in HTML_CONTENT_TYPES or _looks_like_html(body):
        return False
    return urlparse(url).path.lower().endswith(".pdf")


def _is_supported_html_response(content_type: str | None, body: bytes) -> bool:
    normalized_type = detect_content_type(content_type)
    return (
        not normalized_type
        or normalized_type in HTML_CONTENT_TYPES
        or normalized_type in TEXT_LIKE_CONTENT_TYPES
        or normalized_type.endswith("+xml")
        or _looks_like_html(body)
    )


def _response_content_type(response) -> str:
    return response.headers.get("content-type") or response.headers.get("Content-Type") or ""


def download_url(url: str) -> DownloadedContent:
    try:
        response = requests.get(
            url,
            stream=True,
            timeout=settings.ingestion_request_timeout_seconds,
            headers={"User-Agent": "AI-Diplomacy-Briefing-Assistant/1.0"},
        )
    except requests.exceptions.Timeout as exc:
        raise DownloadError("Request timed out while downloading the URL.", status_code=408) from exc
    except requests.exceptions.RequestException as exc:
        raise DownloadError("Could not download URL. Check the URL or network connection.") from exc

    status_code = getattr(response, "status_code", 200)
    if status_code >= 400:
        raise DownloadError(f"Could not download URL. HTTP status {status_code}.", status_code=400)

    content_length = response.headers.get("content-length") or response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > settings.ingestion_max_download_bytes:
                raise OversizedDownloadError("The downloaded file is too large to ingest.")
        except ValueError:
            pass

    chunks = []
    total = 0
    if hasattr(response, "iter_content"):
        iterator = response.iter_content(chunk_size=64 * 1024)
    else:
        iterator = [getattr(response, "content", b"")]
    for chunk in iterator:
        if not chunk:
            continue
        total += len(chunk)
        if total > settings.ingestion_max_download_bytes:
            raise OversizedDownloadError("The downloaded file is too large to ingest.")
        chunks.append(chunk)

    return DownloadedContent(
        url=url,
        content=b"".join(chunks),
        content_type=_response_content_type(response),
    )


def extract_article_from_html(url: str, html: str) -> ExtractedArticle:
    downloaded = sanitize_text(html) or ""
    if not downloaded:
        raise IngestionError("Downloaded page was empty.", status_code=422)

    metadata = trafilatura.extract_metadata(downloaded)
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )

    cleaned = _clean_text(extracted or "")
    if len(cleaned) < 200:
        # Best-effort fallback, in case trafilatura cannot identify enough main content.
        soup = BeautifulSoup(downloaded, "html.parser")
        fallback_text = _clean_text(soup.get_text(separator="\n"))
        if len(fallback_text) > len(cleaned):
            cleaned = fallback_text

    if len(cleaned) < 200:
        raise IngestionError("Extracted text is too short. The page may be blocked or unsuitable.", status_code=422)

    title = None
    published = None

    if metadata:
        title = sanitize_title(metadata.title)
        if metadata.date:
            try:
                published = date.fromisoformat(str(metadata.date)[:10])
            except Exception:
                published = None

    if not title:
        title = _fallback_title_from_url(url)

    return ExtractedArticle(
        title=sanitize_title(title) or "Untitled document",
        raw_text=sanitize_text(extracted, max_chars=settings.ingestion_max_extracted_text_chars) or "",
        cleaned_text=cleaned,
        published_date=published,
    )


def _parse_pdf_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = sanitize_text(value) or ""
    if text.startswith("D:"):
        text = text[2:]
    if len(text) >= 8 and text[:8].isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
    return None


def _is_usable_title(value: str | None) -> bool:
    title = sanitize_title(value)
    if not title:
        return False
    lowered = title.lower()
    if lowered in GENERIC_PDF_TITLES:
        return False
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return False
    if title.endswith(".pdf") and "/" in title:
        return False
    control_or_replacement_count = sum(1 for char in title if ord(char) < 32 or char == "\ufffd")
    if control_or_replacement_count / max(len(title), 1) > 0.05:
        return False
    return len(title) <= 500


def _first_meaningful_line(text: str) -> str | None:
    for line in text.splitlines():
        candidate = sanitize_title(line)
        if not candidate:
            continue
        if len(candidate) < 8:
            continue
        if _is_usable_title(candidate):
            return candidate
    return None


def _filename_title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    filename = unquote(PurePosixPath(parsed.path).name)
    if filename.lower().endswith(".pdf"):
        filename = filename[:-4]
    filename = filename.replace("_", " ").replace("-", " ")
    filename = " ".join(part for part in filename.split() if part)
    return sanitize_title(filename)


def extract_pdf_metadata(pdf_reader: PdfReader) -> dict:
    metadata = pdf_reader.metadata or {}
    title = sanitize_title(getattr(metadata, "title", None) or metadata.get("/Title"))
    created = _parse_pdf_date(getattr(metadata, "creation_date", None) or metadata.get("/CreationDate"))
    modified = _parse_pdf_date(getattr(metadata, "modification_date", None) or metadata.get("/ModDate"))
    return {
        "title": title,
        "published_date": created or modified,
    }


def extract_pdf_title(*, url: str, metadata_title: str | None, text: str) -> str:
    if _is_usable_title(metadata_title):
        return sanitize_title(metadata_title) or "Untitled document"
    first_line = _first_meaningful_line(text)
    if first_line:
        return first_line
    filename_title = _filename_title_from_url(url)
    if _is_usable_title(filename_title):
        return filename_title or "Untitled document"
    return _fallback_title_from_url(url)


def _meaningful_text_score(text: str) -> int:
    return sum(1 for char in text if char.isalpha() or char.isdigit())


def _validate_meaningful_pdf_text(cleaned: str) -> None:
    if len(cleaned) < 80 or _meaningful_text_score(cleaned) < 40:
        raise PDFNoExtractableTextError(
            "This PDF does not contain extractable text. OCR is not supported yet.",
            status_code=422,
        )
    lower = cleaned.lower()
    if "%pdf-" in lower or " obj" in lower[:500] or "endstream" in lower[:1000]:
        raise PDFParseError("Could not parse this PDF into readable text.", status_code=422)


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, PdfReader]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    except Exception as exc:
        raise PDFParseError("Could not parse this PDF.", status_code=422) from exc

    if getattr(reader, "is_encrypted", False):
        try:
            if reader.decrypt("") == 0:
                raise PDFParseError("This PDF is encrypted or password-protected.", status_code=422)
        except Exception as exc:
            raise PDFParseError("This PDF is encrypted or password-protected.", status_code=422) from exc

    page_texts = []
    try:
        for page in reader.pages:
            text = page.extract_text() or ""
            text = sanitize_text(text)
            if text:
                page_texts.append(text)
    except Exception as exc:
        raise PDFParseError("Could not extract readable text from this PDF.", status_code=422) from exc

    raw_text = "\n\n".join(page_texts)
    raw_text = sanitize_text(raw_text, max_chars=settings.ingestion_max_extracted_text_chars) or ""
    return raw_text, reader


def extract_article_from_pdf(url: str, pdf_bytes: bytes) -> ExtractedArticle:
    raw_text, reader = extract_pdf_text(pdf_bytes)
    cleaned = _clean_text(raw_text)
    _validate_meaningful_pdf_text(cleaned)
    metadata = extract_pdf_metadata(reader)
    title = extract_pdf_title(url=url, metadata_title=metadata.get("title"), text=cleaned)
    return ExtractedArticle(
        title=sanitize_title(title) or "Untitled document",
        raw_text=raw_text,
        cleaned_text=cleaned,
        published_date=metadata.get("published_date"),
    )


def extract_article_from_url(url: str) -> ExtractedArticle:
    downloaded = download_url(url)
    if is_pdf_response(content_type=downloaded.content_type, body=downloaded.content, url=url):
        return extract_article_from_pdf(url, downloaded.content)

    if not _is_supported_html_response(downloaded.content_type, downloaded.content):
        raise UnsupportedContentTypeError("Unsupported content type for URL ingestion.")

    encoding = "utf-8"
    html = downloaded.content.decode(encoding, errors="replace")
    return extract_article_from_html(url, html)


def ingest_url(
    db: Session,
    *,
    url: str,
    source_id: int | None = None,
    topic_tags: str | None = None,
    sensitivity_level: str = "medium",
    language: str | None = None,
) -> Document:
    existing = db.query(Document).filter(Document.url == url).first()
    if existing:
        raise DuplicateDocumentError(f"Document already exists with id={existing.id}", status_code=400)

    if source_id is not None:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise IngestionError(f"Source with id={source_id} does not exist.", status_code=400)

    article = extract_article_from_url(url)

    try:
        document = Document(
            source_id=source_id,
            title=sanitize_title(article.title) or "Untitled document",
            url=url,
            published_date=article.published_date,
            language=sanitize_text(language, max_chars=50),
            raw_text=sanitize_text(article.raw_text, max_chars=settings.ingestion_max_extracted_text_chars),
            cleaned_text=sanitize_text(article.cleaned_text, max_chars=settings.ingestion_max_extracted_text_chars),
            topic_tags=sanitize_text(topic_tags),
            sensitivity_level=sanitize_text(sensitivity_level, max_chars=50) or "medium",
            status="ingested",
        )

        db.add(document)
        db.flush()
        assign_document_to_event(db, document_id=document.id)

        create_audit_log(
            db,
            action="ingest_url",
            entity_type="document",
            entity_id=str(document.id),
            details=f"Ingested URL: {url}",
        )
        db.refresh(document)
    except IngestionError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise IngestionError("Ingestion failed. The document could not be saved safely.", status_code=500) from exc

    return document
