"""Streamlit UI for Lead Qualification Agent."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8003")

st.set_page_config(page_title="Lead Qualification", page_icon="🎯")
st.title("🎯 Lead Qualification Agent")
st.caption("Deterministic scoring + AI explanation")

tab1, tab2 = st.tabs(["Score Lead", "History"])

with tab1:
    with st.form("lead_form"):
        col1, col2 = st.columns(2)
        company = col1.text_input("Company Name *")
        contact = col2.text_input("Contact Name *")
        industry = col1.selectbox("Industry", ["technology", "finance", "healthcare", "retail", "education", "other"])
        budget = col2.selectbox("Budget Range", ["under_10k", "10k_50k", "50k_100k", "100k_250k", "over_250k"])
        timeline = col1.selectbox("Timeline", ["immediately", "within_3_months", "within_6_months", "within_year", "no_timeline"])
        use_case = st.text_area("Use Case Description", max_chars=1000)
        submitted = st.form_submit_button("Score Lead", type="primary")

    if submitted and company and contact:
        with st.spinner("Scoring..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/score",
                    json={"company": company, "contact": contact, "industry": industry,
                          "budget": budget, "timeline": timeline, "use_case": use_case},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                score = data["score"]
                color = "🟢" if score >= 70 else ("🟡" if score >= 40 else "🔴")
                st.metric("Lead Score", f"{color} {score}/100")
                st.subheader("Score Breakdown")
                cols = st.columns(4)
                for i, (k, v) in enumerate(data["breakdown"].items()):
                    cols[i % 4].metric(k.capitalize(), v)
                st.subheader("AI Explanation")
                st.info(data["explanation"])
                st.subheader("Follow-up Email Draft")
                st.text_area("Email", data["email_draft"], height=200)
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Lead History")
    try:
        resp = httpx.get(f"{API_URL}/history", params={"limit": 20}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        st.caption(f"Total: {data['total']} leads")
        for item in data["items"]:
            with st.expander(f"[{item['score']}/100] {item['company']} — {item['contact']}"):
                st.write(f"**Industry:** {item['industry']} | **Budget:** {item['budget']} | **Timeline:** {item['timeline']}")
                st.write(f"**Explanation:** {item['explanation']}")
    except Exception as e:
        st.error(f"Could not load history: {e}")
