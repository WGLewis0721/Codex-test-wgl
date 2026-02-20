"""Streamlit UI for Knowledge Copilot Agent."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8002")

st.set_page_config(page_title="Knowledge Copilot", page_icon="📚")
st.title("📚 Knowledge Copilot")
st.caption("Document-grounded Q&A with citations")

tab1, tab2 = st.tabs(["Ask", "Documents"])

with tab1:
    query = st.text_input("Ask a question", placeholder="What is the return policy?")
    top_k = st.slider("Results to retrieve", 1, 10, 5)
    if st.button("Ask", type="primary", disabled=not query.strip()):
        with st.spinner("Searching knowledge base..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/chat",
                    json={"query": query, "top_k": top_k},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                st.subheader("Answer")
                st.write(data["answer"])
                if data["sources"]:
                    st.subheader("Sources")
                    for src in data["sources"]:
                        st.badge(src)
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Upload Document")
    uploaded = st.file_uploader("Upload PDF, TXT, or MD", type=["pdf", "txt", "md"])
    if uploaded and st.button("Ingest Document"):
        with st.spinner("Processing..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/ingest",
                    files={"file": (uploaded.name, uploaded.read(), "application/octet-stream")},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                st.success(f"Ingested {data['chunks']} chunks from {data['filename']}")
            except Exception as e:
                st.error(f"Error: {e}")

    st.subheader("Uploaded Documents")
    try:
        resp = httpx.get(f"{API_URL}/docs", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        st.caption(f"Total: {data['total']} documents")
        for doc in data["documents"]:
            st.text(f"📄 {doc['filename']} ({doc['chunk_count']} chunks) — {doc['created_at']}")
    except Exception as e:
        st.error(f"Could not load documents: {e}")
