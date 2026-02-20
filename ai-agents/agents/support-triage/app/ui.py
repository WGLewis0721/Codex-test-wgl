"""Streamlit UI for Support Triage Agent."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8001")

st.set_page_config(page_title="Support Triage Agent", page_icon="🎫")
st.title("🎫 Support Triage Agent")
st.caption("AI-powered support ticket analysis and routing")

tab1, tab2 = st.tabs(["Analyze Ticket", "History"])

with tab1:
    ticket_text = st.text_area("Support Ticket", height=200, placeholder="Describe your issue here...")
    if st.button("Analyze", type="primary", disabled=not ticket_text.strip()):
        with st.spinner("Analyzing..."):
            try:
                resp = httpx.post(f"{API_URL}/analyze", json={"ticket_text": ticket_text}, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                col1, col2 = st.columns(2)
                urgency_colors = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
                col1.metric("Urgency", f"{urgency_colors.get(data['urgency'], '⚪')} {data['urgency'].upper()}")
                col2.metric("Sentiment", data["sentiment"].capitalize())
                col1.metric("Domain", data["domain"].capitalize())
                col2.metric("Route To", data["routing"].capitalize())
                st.subheader("Draft Response")
                st.info(data["draft_response"])
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Analysis History")
    if st.button("Refresh"):
        st.rerun()
    try:
        resp = httpx.get(f"{API_URL}/history", params={"limit": 20, "offset": 0}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        st.caption(f"Total: {data['total']} analyses")
        for item in data["items"]:
            with st.expander(f"[{item['urgency'].upper()}] {item['ticket_text'][:60]}..."):
                st.write(f"**Sentiment:** {item['sentiment']} | **Domain:** {item['domain']} | **Routing:** {item['routing']}")
                st.write(f"**Draft Response:** {item['draft_response']}")
                st.caption(item["created_at"])
    except Exception as e:
        st.error(f"Could not load history: {e}")
