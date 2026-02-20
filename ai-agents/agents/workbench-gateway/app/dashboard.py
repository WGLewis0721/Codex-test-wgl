"""Streamlit dashboard for Workbench Gateway."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8006")

st.set_page_config(page_title="AI Workbench Gateway", page_icon="🔧")
st.title("🔧 AI Workbench Gateway")
st.caption("OpenAI-compatible local LLM gateway")

tab1, tab2 = st.tabs(["Dashboard", "Test"])

with tab1:
    st.subheader("Gateway Status")
    try:
        resp = httpx.get(f"{API_URL}/health", timeout=5)
        resp.raise_for_status()
        st.success("Gateway Online ✅")
    except Exception:
        st.error("Gateway Offline ❌")

    st.subheader("Available Models")
    try:
        resp = httpx.get(f"{API_URL}/v1/models", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("data", [])
        if models:
            for model in models:
                st.write(f"✅ `{model['id']}`")
        else:
            st.info("No models currently available in Ollama")
    except Exception as e:
        st.warning(f"Could not fetch models: {e}")

    st.subheader("Request Metrics")
    if st.button("Refresh Metrics"):
        st.rerun()
    try:
        resp = httpx.get(f"{API_URL}/dashboard", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        st.subheader("Recent Requests")
        for req in data.get("recent_requests", [])[:10]:
            st.text(f"[{req['status']}] {req['model']} | {req['prompt_tokens']}+{req['completion_tokens']} tokens | {req['created_at']}")
    except Exception as e:
        st.error(f"Could not load metrics: {e}")

with tab2:
    st.subheader("Test Chat Completion")
    model = st.selectbox("Model", ["phi3:medium", "llama3.2:3b", "mistral:7b"])
    test_prompt = st.text_area("Prompt", placeholder="Enter a test prompt...")
    client_id = st.text_input("Client ID (optional)", value="test-user")
    if st.button("Send", type="primary", disabled=not test_prompt.strip()):
        with st.spinner("Sending request..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/v1/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": test_prompt}]},
                    headers={"X-Client-ID": client_id},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                st.subheader("Response")
                st.write(data["choices"][0]["message"]["content"])
                st.caption(f"Tokens: {data['usage']['total_tokens']} | Model: {data['model']}")
            except Exception as e:
                st.error(f"Error: {e}")
