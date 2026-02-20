"""Streamlit UI for Interview Fit Agent."""
import streamlit as st
import httpx
import os

API_URL = os.getenv("API_URL", "http://localhost:8005")

st.set_page_config(page_title="Interview Fit Agent", page_icon="💼")
st.title("💼 Interview Fit Agent")
st.caption("Resume + JD analysis with interview prep")

tab1, tab2 = st.tabs(["Analyze", "Exports"])

with tab1:
    col1, col2 = st.columns(2)
    resume_file = col1.file_uploader("Upload Resume (PDF)", type=["pdf"])
    jd_text = col2.text_area("Job Description", height=300, placeholder="Paste the job description here...")

    if st.button("Analyze Fit", type="primary", disabled=not (resume_file and jd_text.strip())):
        with st.spinner("Analyzing fit..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/analyze",
                    files={"resume_file": (resume_file.name, resume_file.read(), "application/pdf")},
                    data={"jd_text": jd_text},
                    timeout=180,
                )
                resp.raise_for_status()
                data = resp.json()
                grade_colors = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "🔴"}
                st.metric("Fit Grade", f"{grade_colors.get(data['fit_grade'], '⚪')} {data['fit_grade']}")

                col1, col2 = st.columns(2)
                col1.subheader("Strengths")
                for s in data.get("strengths", []):
                    col1.write(f"✅ {s}")
                col2.subheader("Gaps")
                for g in data.get("gaps", []):
                    col2.write(f"⚠️ {g}")

                st.subheader("Interview Q&A Prep")
                for i, qa in enumerate(data.get("qa_pairs", []), 1):
                    with st.expander(f"Q{i}: {qa.get('question', '')}"):
                        st.write(qa.get("answer", ""))

                st.subheader("Study Plan")
                for topic in data.get("study_plan", []):
                    st.write(f"📖 {topic}")
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Analysis Exports")
    try:
        resp = httpx.get(f"{API_URL}/exports", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        st.caption(f"Total: {data['total']} analyses")
        for exp in data["exports"]:
            st.text(f"Grade {exp['fit_grade']} — {exp['jd_summary']} ({exp['created_at']})")
    except Exception as e:
        st.error(f"Could not load exports: {e}")
