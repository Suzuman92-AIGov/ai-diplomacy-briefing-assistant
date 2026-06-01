from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.source import Source
from app.services.audit import create_audit_log


@dataclass
class ExtractedArticle:
    title: str
    raw_text: str
    cleaned_text: str
    published_date: date | None = None


def _fallback_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("-", " ").replace("_", " ")
    if path:
        return path[:120].title()
    return parsed.netloc or "Untitled document"


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines)


def extract_article_from_url(url: str) -> ExtractedArticle:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("Could not download URL. Check the URL or network connection.")

    metadata = trafilatura.extract_metadata(downloaded)
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )

    if not extracted:
        # Best-effort fallback, in case trafilatura cannot identify the main content.
        soup = BeautifulSoup(downloaded, "html.parser")
        extracted = soup.get_text(separator="\n")

    cleaned = _clean_text(extracted or "")
    if len(cleaned) < 200:
        raise ValueError("Extracted text is too short. The page may be blocked or unsuitable.")

    title = None
    published = None

    if metadata:
        title = metadata.title
        if metadata.date:
            try:
                published = date.fromisoformat(str(metadata.date)[:10])
            except Exception:
                published = None

    if not title:
        title = _fallback_title_from_url(url)

    return ExtractedArticle(
        title=title[:500],
        raw_text=extracted,
        cleaned_text=cleaned,
        published_date=published,
    )


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
        raise ValueError(f"Document already exists with id={existing.id}")

    if source_id is not None:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise ValueError(f"Source with id={source_id} does not exist.")

    article = extract_article_from_url(url)

    document = Document(
        source_id=source_id,
        title=article.title,
        url=url,
        published_date=article.published_date,
        language=language,
        raw_text=article.raw_text,
        cleaned_text=article.cleaned_text,
        topic_tags=topic_tags,
        sensitivity_level=sensitivity_level,
        status="ingested",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    create_audit_log(
        db,
        action="ingest_url",
        entity_type="document",
        entity_id=str(document.id),
        details=f"Ingested URL: {url}",
    )

    return document
