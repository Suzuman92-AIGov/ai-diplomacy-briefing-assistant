from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.search import semantic_search


def _make_excerpt(text: str, max_chars: int = 650) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _build_citations(results: list[dict]) -> list[dict]:
    citations = []
    for idx, item in enumerate(results, start=1):
        citations.append(
            {
                "citation_id": f"[{idx}]",
                "chunk_id": item["chunk_id"],
                "document_id": item["document_id"],
                "title": item["title"],
                "url": item["url"],
                "source_name": item.get("source_name"),
                "reliability_tier": item.get("reliability_tier"),
                "published_date": item.get("published_date"),
                "excerpt": _make_excerpt(item["content"]),
            }
        )
    return citations


def _local_extractive_answer(question: str, results: list[dict]) -> str:
    if not results:
        return (
            "I could not find enough source material in the local knowledge base "
            "to answer this question. Add or ingest more relevant documents first."
        )

    top = results[:3]
    bullet_lines = []

    for idx, item in enumerate(top, start=1):
        excerpt = _make_excerpt(item["content"], max_chars=420)
        title = item["title"]
        bullet_lines.append(f"- [{idx}] {title}: {excerpt}")

    return (
        "Based on the retrieved source chunks, the answer appears to be:\n\n"
        + "\n".join(bullet_lines)
        + "\n\n"
        "This is a local extractive answer. It does not add claims beyond the retrieved text. "
        "For a more polished synthesis, switch ANSWER_PROVIDER=openai when API billing is available."
    )


def _openai_answer(question: str, results: list[dict]) -> str:
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
You are an AI foreign policy briefing assistant.

Answer the user's question using only the provided source chunks.
Do not add facts that are not supported by the sources.
If the sources are insufficient, say so.
Cite claims using bracket citations like [1], [2].
Keep the answer concise and policy-briefing style.

Question:
{question}

Source chunks:
{chr(10).join(source_blocks)}
""".strip()

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": "You generate source-grounded policy briefing answers."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


def answer_question(db: Session, *, question: str, top_k: int = 5) -> dict:
    results = semantic_search(db, query=question, top_k=top_k)
    citations = _build_citations(results)

    if settings.answer_provider.lower() == "openai":
        answer = _openai_answer(question, results)
    else:
        answer = _local_extractive_answer(question, results)

    return {
        "question": question,
        "answer": answer,
        "answer_provider": settings.answer_provider,
        "retrieval_provider": settings.embedding_provider,
        "citations": citations,
    }
