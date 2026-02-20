"""FastAPI server for Interview Fit agent."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from shared.schemas import HealthResponse
from shared.utils import extract_text_from_file
from agent.analyzer import analyze_fit, build_markdown_report
from agent.storage import init_db, save_analysis, save_export, list_exports

app = FastAPI(title="Interview Fit API", version="1.0.0")
init_db()


class FitResponse(BaseModel):
    fit_grade: str
    strengths: list[str]
    gaps: list[str]
    qa_pairs: list[dict]
    study_plan: list
    export_path: str | None = None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "interview-fit"})


@app.post("/analyze", response_model=FitResponse)
async def analyze(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
) -> FitResponse:
    if not resume_file.filename or not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are accepted")
    resume_bytes = await resume_file.read()
    resume_text = extract_text_from_file(resume_bytes, resume_file.filename)
    result = analyze_fit(resume_text, jd_text)
    jd_summary = jd_text[:80]
    markdown = build_markdown_report(result, jd_summary)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    export_path = save_export(markdown, f"fit_analysis_{ts}.md")
    save_analysis(result["fit_grade"], jd_summary, export_path)
    return FitResponse(**result, export_path=export_path)


@app.get("/exports")
def get_exports() -> dict:
    exports = list_exports()
    return {"exports": exports, "total": len(exports)}
