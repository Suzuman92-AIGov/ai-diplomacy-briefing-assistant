import re
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.brief import Brief, BriefSource
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import Source
from app.services.audit import create_audit_log

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPORT_DIR = PROJECT_ROOT / "exports"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] or "brief"



def build_brief_markdown(db: Session, *, brief_id: int) -> tuple[str, str]:
    brief = db.query(Brief).filter(Brief.id == brief_id).first()
    if not brief:
        raise ValueError(f"Brief with id={brief_id} does not exist.")

    source_rows = (
        db.query(BriefSource, Document, Chunk, Source)
        .outerjoin(Document, BriefSource.document_id == Document.id)
        .outerjoin(Chunk, BriefSource.chunk_id == Chunk.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .filter(BriefSource.brief_id == brief_id)
        .order_by(BriefSource.id.asc())
        .all()
    )

    source_table = [
        "| Citation | Source | Reliability | URL |",
        "|---|---|---|---|",
    ]

    for brief_source, document, chunk, source in source_rows:
        source_table.append(
            f"| {brief_source.citation_label} | {document.title if document else 'Unknown'} | "
            f"{source.reliability_tier if source else 'Unknown'} | {document.url if document else ''} |"
        )

    lines = [
        f"# {brief.title}",
        "",
        "> Draft policy briefing output generated from retrieved public-source material.",
        "",
        "## Metadata",
        "",
        f"- **Brief ID:** {brief.id}",
        f"- **Type:** {brief.brief_type}",
        f"- **Topic:** {brief.query_or_topic or ''}",
        f"- **Review status:** {brief.review_status}",
        f"- **Sensitivity:** {brief.sensitivity_level}",
        f"- **Confidence:** {brief.confidence_level}",
        f"- **Created at:** {brief.created_at}",
        f"- **Updated at:** {brief.updated_at}",
        "",
        "## Brief Content",
        "",
        brief.content,
        "",
        "## Review Information",
        "",
        f"- **Review status:** {brief.review_status}",
        f"- **Reviewer notes:** {brief.reviewer_notes or 'No reviewer notes.'}",
        "",
        "## Source Table",
        "",
        "\n".join(source_table) if source_rows else "_No sources linked._",
        "",
        "## Source Excerpts",
        "",
    ]

    if not source_rows:
        lines.append("_No source excerpts available._")
    else:
        for brief_source, document, chunk, source in source_rows:
            lines.extend(
                [
                    f"### {brief_source.citation_label} {document.title if document else 'Unknown document'}",
                    "",
                    f"- **URL:** {document.url if document else ''}",
                    f"- **Source:** {source.name if source else 'Unknown'}",
                    f"- **Reliability:** {source.reliability_tier if source else 'Unknown'}",
                    f"- **Document ID:** {document.id if document else ''}",
                    f"- **Chunk ID:** {chunk.id if chunk else ''}",
                    "",
                    "#### Excerpt",
                    "",
                    (chunk.content[:1400] if chunk and chunk.content else "_No excerpt available._"),
                    "",
                ]
            )

    lines.extend(
        [
            "## Governance Disclaimer",
            "",
            "This document is a draft generated from retrieved public-source material. It is not an official position and should be reviewed by a human before external circulation or publication.",
            "",
        ]
    )

    filename = f"brief_{brief.id}_{_slugify(brief.title)}.md"
    return filename, "\n".join(lines)

def export_brief_markdown(db: Session, *, brief_id: int, actor: str = "demo_user") -> dict:
    filename, markdown = build_brief_markdown(db, brief_id=brief_id)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EXPORT_DIR / filename
    output_path.write_text(markdown, encoding="utf-8")

    create_audit_log(
        db,
        action="export_brief_markdown",
        entity_type="brief",
        entity_id=str(brief_id),
        actor=actor,
        details=f"Exported brief to {output_path}",
    )

    return {
        "status": "ok",
        "brief_id": brief_id,
        "filename": filename,
        "path": str(output_path),
        "markdown": markdown,
    }
