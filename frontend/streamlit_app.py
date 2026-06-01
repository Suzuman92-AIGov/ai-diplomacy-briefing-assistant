import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv("../.env")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Diplomacy Briefing Assistant", page_icon="🛰️", layout="wide")
st.title("AI Diplomacy Briefing Assistant")
st.caption("RAG-based policy briefing assistant for AI governance and foreign policy monitoring.")

page = st.sidebar.radio("Go to", ["Start Here",
        "Dashboard",
        "System Status", "Sources",
        "Source Pack", "Ingest URL", "Documents", "Semantic Search",
        "Ask Knowledge Base",
        "Generate Brief",
        "Review Briefs",
        "Export Brief", "Briefs", "Audit Logs", "Governance"])

def api_get(path: str, params: dict | None = None):
    r = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def api_post(path: str, payload: dict | None = None):
    r = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()



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
                result = api_post("/sources", {"name": name, "base_url": base_url, "source_type": source_type, "reliability_tier": reliability_tier, "country_or_institution": country_or_institution, "notes": notes, "is_active": is_active})
                st.success(f"Created source: {result['name']}")
            except Exception as exc: st.error("Could not create source."); st.code(str(exc))
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
    source_options = {"No source selected": None} | {f"{s['id']} — {s['name']} ({s['reliability_tier']})": s["id"] for s in sources}
    with st.form("ingest_url_form"):
        url = st.text_input("Public URL", value="https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai")
        source_label = st.selectbox("Source", list(source_options.keys()))
        topic_tags = st.text_input("Topic tags", value="EU AI Act, AI governance, regulation")
        sensitivity_level = st.selectbox("Sensitivity level", ["low", "medium", "high", "critical"], index=1)
        language = st.text_input("Language", value="English")
        if st.form_submit_button("Ingest URL"):
            try:
                with st.spinner("Extracting and saving document..."):
                    st.json(api_post("/ingest/url", {"url": url, "source_id": source_options[source_label], "topic_tags": topic_tags, "sensitivity_level": sensitivity_level, "language": language}))
                st.success("Document ingested.")
            except Exception as exc: st.error("Could not ingest URL."); st.code(str(exc))


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
