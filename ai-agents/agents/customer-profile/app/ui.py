"""Streamlit UI for Customer Profile Builder."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8004")

st.set_page_config(page_title="Customer Profile Builder", page_icon="👤")
st.title("👤 Customer Profile Builder")
st.caption("Structured technical profile with versioned history")

tab1, tab2 = st.tabs(["Build Profile", "View History"])

with tab1:
    with st.form("profile_form"):
        st.subheader("Step 1: Customer Info")
        col1, col2 = st.columns(2)
        customer_id = col1.text_input("Customer ID *")
        company = col2.text_input("Company Name *")
        industry = col1.selectbox("Industry", ["technology", "finance", "healthcare", "retail", "education", "other"])
        team_size = col2.selectbox("Team Size", ["1-50", "51-200", "201-1000", "1000+"])

        st.subheader("Step 2: Technical Details")
        current_stack = st.text_area("Current Technology Stack", height=100)
        pain_points = st.text_area("Pain Points", height=100)
        goals = st.text_area("Goals", height=100)

        st.subheader("Step 3: Requirements")
        compliance = st.text_input("Compliance Requirements (e.g., SOC2, HIPAA)")
        budget = st.selectbox("Budget Range", ["under_50k", "50k_200k", "200k_500k", "over_500k", "unknown"])

        submitted = st.form_submit_button("Build Profile", type="primary")

    if submitted and customer_id and company:
        with st.spinner("Building profile..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/profile",
                    json={"customer_id": customer_id, "company": company, "industry": industry,
                          "team_size": team_size, "current_stack": current_stack,
                          "pain_points": pain_points, "goals": goals,
                          "compliance": compliance, "budget": budget},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                profile = data["profile"]
                st.success(f"Profile v{data['version']} created!")
                st.subheader("Summary")
                st.write(profile["summary"])
                col1, col2 = st.columns(2)
                col1.subheader("Recommended Services")
                for svc in profile.get("recommended_services", []):
                    col1.write(f"• {svc}")
                col2.subheader("Priority Actions")
                for action in profile.get("priority_actions", []):
                    col2.write(f"• {action}")
                st.subheader("Markdown Export")
                st.download_button("Download Markdown", data["markdown"], file_name=f"{customer_id}_v{data['version']}.md")
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    cid = st.text_input("Enter Customer ID to view history")
    if st.button("Load History") and cid:
        try:
            resp = httpx.get(f"{API_URL}/profiles/{cid}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for v in data["versions"]:
                with st.expander(f"v{v['version']} — {v['company']} ({v['created_at']})"):
                    st.write(f"**Industry:** {v['industry']}")
        except Exception as e:
            st.error(f"Error: {e}")
