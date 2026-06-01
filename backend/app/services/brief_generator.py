from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brief import Brief, BriefSource
from app.services.audit import create_audit_log
from app.services.search import semantic_search


def _shorten(text: str, max_chars: int = 600) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _classify_sensitivity(topic: str, source_text: str) -> str:
    combined = f"{topic}\n{source_text}".lower()
    high_terms = [
        "military", "war", "conflict", "sanction", "export control", "surveillance",
        "biometric", "election", "cyber", "national security", "intelligence",
        "china", "russia", "weapon", "disinformation", "human rights abuse",
    ]
    medium_terms = [
        "regulation", "governance", "government", "policy", "public sector",
        "risk management", "standard", "compliance", "data protection",
    ]

    if any(term in combined for term in high_terms):
        return "high"
    if any(term in combined for term in medium_terms):
        return "medium"
    return "low"



def _local_policy_brief(topic: str, audience: str, results: list[dict]) -> str:
    if not results:
        return (
            f"# Policy Brief: {topic}\n\n"
            "## Executive Summary\n\n"
            "The local knowledge base does not contain enough relevant source material to generate a grounded brief.\n\n"
            "## Source Support\n\n"
            "Insufficient source support. Add or ingest more relevant public documents first.\n"
        )

    source_text = "\n\n".join(item["content"] for item in results[:6])
    sensitivity = _classify_sensitivity(topic, source_text)

    unique_sources = []
    seen_titles = set()
    for item in results:
        title = item["title"]
        if title not in seen_titles:
            seen_titles.add(title)
            unique_sources.append(item)

    high_reliability_count = sum(1 for item in results if item.get("reliability_tier") == "high")
    evidence_strength = "High" if len(unique_sources) >= 3 and high_reliability_count >= 3 else "Medium" if len(results) >= 3 else "Low"

    evidence_reason = (
        f"Based on {len(results)} retrieved chunks from {len(unique_sources)} unique source(s), "
        f"including {high_reliability_count} chunk(s) from high-reliability sources."
    )

    key_items = []
    for idx, item in enumerate(results[:5], start=1):
        reliability = item.get("reliability_tier") or "unknown reliability"
        key_items.append(
            f"{idx}. **{item['title']}** ({reliability}) — {_shorten(item['content'], 430)}"
        )

    clear_points = []
    for idx, item in enumerate(results[:3], start=1):
        clear_points.append(
            f"- The retrieved material from **{item['title']}** supports this topic as relevant to AI governance and public policy. [{idx}]"
        )

    source_lines = [
        f"- [{i}] {item['title']} — {item['url']}"
        for i, item in enumerate(results[:6], start=1)
    ]

    return f"""# Policy Brief: {topic}

## Executive Summary

This brief is based on retrieved public-source material from the local knowledge base. The available source base indicates that **{topic}** is relevant to AI governance, institutional risk management, regulatory coordination, public-sector adoption, and international standard-setting.

## Key Developments / Source Findings

{chr(10).join(key_items)}

## Why It Matters

AI governance is increasingly becoming a practical policy issue rather than only a technical discussion. For public diplomacy and international affairs teams, the topic matters because it connects innovation, trust, risk management, regulation, standards, and institutional legitimacy.

## Foreign Policy Relevance

For a public diplomacy or policy team, this topic can be framed as part of a broader international conversation on responsible AI, trustworthy technology, democratic governance, standards, and cross-border cooperation. Where the sources concern official frameworks or public institutions, they may signal how governments and international partners define acceptable AI risk.

## What Is Clear From the Retrieved Sources

{chr(10).join(clear_points)}

## What Remains Unclear / Needs Human Review

- The retrieved chunks may not cover the full institutional or geopolitical context.
- Any claim about official policy positions should be checked against the original source pages.
- Sensitive interpretations should be reviewed before external communication.

## Risk / Opportunity

**Opportunity:** The topic can support communication around responsible innovation, transparency, risk management, human oversight, and international cooperation.

**Risk:** The brief should not overstate official positions beyond the source material. Sensitive or geopolitical interpretations require human review.

## Evidence Strength

**{evidence_strength}**

Reason: {evidence_reason}

## Sensitivity Level

**{sensitivity.upper()}**

## Suggested Internal Use

This brief is suitable as an internal first-draft briefing note, meeting preparation aid, or starting point for public diplomacy planning. It should not be treated as a final external communication without review.

## Suggested Public Diplomacy Angle

A safe public diplomacy angle would emphasize responsible AI, risk-aware innovation, transparency, human oversight, and cooperation among trusted institutions.

## Sources Used

{chr(10).join(source_lines)}

## Governance Note

This is a local extractive/synthetic brief generated from retrieved chunks. It should be treated as a draft, not as an official position. Human review is required before external use.
"""

def _openai_policy_brief(topic: str, audience: str, results: list[dict]) -> str:
    if not settings.openai_api_key or settings.openai_api_key == "your_api_key_here":
        raise ValueError("OPENAI_API_KEY is missing. Use ANSWER_PROVIDER=local or add a valid API key.")

    client = OpenAI(api_key=settings.openai_api_key)

    source_blocks = []
    for idx, item in enumerate(results, start=1):
        source_blocks.append(
            f"[{idx}] Title: {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Source: {item.get('source_name') or 'Unknown'}\n"
            f"Reliability: {item.get('reliability_tier') or 'Unknown'}\n"
            f"Text:\n{item['content']}\n"
        )

    prompt = f"""
You are an AI foreign policy briefing assistant for a public diplomacy and policy team.

Generate a concise policy brief for this audience: {audience}

Topic:
{topic}

Use only the source chunks below. Do not add unsupported facts.
If the sources are insufficient, say so clearly.
Cite source numbers like [1], [2] where relevant.

Required structure:
1. Executive Summary
2. Key Developments / Source Findings
3. Why It Matters
4. Foreign Policy Relevance
5. Risk / Opportunity
6. Sensitivity Level
7. Suggested Public Diplomacy Angle
8. Sources Used
9. Governance Note

Source chunks:
{chr(10).join(source_blocks)}
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": "You generate source-grounded foreign policy and AI governance briefs."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


def generate_policy_brief(db: Session, *, topic: str, audience: str, top_k: int = 6) -> dict:
    results = semantic_search(db, query=topic, top_k=top_k)

    if settings.answer_provider.lower() == "openai":
        content = _openai_policy_brief(topic, audience, results)
    else:
        content = _local_policy_brief(topic, audience, results)

    title = f"AI Foreign Policy Brief: {topic}"
    source_text = "\n".join(item["content"] for item in results[:5])
    sensitivity = _classify_sensitivity(topic, source_text)

    brief = Brief(
        title=title,
        brief_type="policy_brief",
        query_or_topic=topic,
        content=content,
        executive_summary=None,
        sensitivity_level=sensitivity,
        confidence_level="medium" if results else "low",
        review_status="draft",
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)

    for idx, item in enumerate(results[:top_k], start=1):
        db.add(
            BriefSource(
                brief_id=brief.id,
                document_id=item["document_id"],
                chunk_id=item["chunk_id"],
                citation_label=f"[{idx}]",
            )
        )

    db.commit()

    create_audit_log(
        db,
        action="generate_policy_brief",
        entity_type="brief",
        entity_id=str(brief.id),
        details=f"Generated policy brief for topic: {topic}",
    )

    return {
        "title": title,
        "topic": topic,
        "audience": audience,
        "content": content,
        "answer_provider": settings.answer_provider,
        "retrieval_provider": settings.embedding_provider,
        "brief_id": brief.id,
        "sources": results[:top_k],
    }
