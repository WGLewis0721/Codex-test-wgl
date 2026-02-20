"""Resume and JD analysis for Interview Fit agent."""
from __future__ import annotations
import json
import re
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.ollama import chat
from shared.logging import get_logger
from .prompts import FIT_SYSTEM, FIT_PROMPT

logger = get_logger(__name__)

VALID_GRADES = {"A", "B", "C", "D", "F"}


def analyze_fit(resume_text: str, jd_text: str) -> dict[str, Any]:
    """Analyze resume vs JD and return fit analysis."""
    if not resume_text.strip():
        raise ValueError("Resume text is empty")
    if not jd_text.strip():
        raise ValueError("Job description is empty")

    prompt = FIT_PROMPT.format(
        resume_text=resume_text[:4000],
        jd_text=jd_text[:2000],
    )
    try:
        raw = chat(prompt=prompt, system=FIT_SYSTEM, max_tokens=2048)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(match.group()) if match else {}
    except Exception as exc:
        logger.error(f"Fit analysis failed: {exc}")
        result = {}

    grade = result.get("fit_grade", "C")
    if grade not in VALID_GRADES:
        grade = "C"

    return {
        "fit_grade": grade,
        "strengths": result.get("strengths", []),
        "gaps": result.get("gaps", []),
        "qa_pairs": result.get("qa_pairs", [])[:10],
        "study_plan": result.get("study_plan", []),
    }


def build_markdown_report(analysis: dict[str, Any], jd_summary: str) -> str:
    """Generate markdown export of interview analysis."""
    lines = [
        f"# Interview Fit Analysis",
        f"\n**Fit Grade:** {analysis['fit_grade']}",
        f"**Position:** {jd_summary[:100]}",
        "\n## Strengths",
    ]
    for s in analysis.get("strengths", []):
        lines.append(f"- {s}")
    lines.append("\n## Gaps to Address")
    for g in analysis.get("gaps", []):
        lines.append(f"- {g}")
    lines.append("\n## Interview Q&A Prep")
    for i, qa in enumerate(analysis.get("qa_pairs", []), 1):
        lines.append(f"\n### Q{i}: {qa.get('question', '')}")
        lines.append(f"**A:** {qa.get('answer', '')}")
    lines.append("\n## Study Plan")
    for topic in analysis.get("study_plan", []):
        lines.append(f"- {topic}")
    return "\n".join(lines)
