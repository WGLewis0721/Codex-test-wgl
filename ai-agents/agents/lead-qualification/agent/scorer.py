"""Deterministic rubric scoring + LLM explanation for lead qualification."""
from __future__ import annotations
import json
import re
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.ollama import chat
from shared.logging import get_logger
from .prompts import LEAD_EXPLANATION_SYSTEM, LEAD_EXPLANATION_PROMPT

logger = get_logger(__name__)

BUDGET_SCORES = {
    "under_10k": 5,
    "10k_50k": 15,
    "50k_100k": 25,
    "100k_250k": 35,
    "over_250k": 40,
}

TIMELINE_SCORES = {
    "immediately": 20,
    "within_3_months": 18,
    "within_6_months": 14,
    "within_year": 8,
    "no_timeline": 2,
}

INDUSTRY_SCORES = {
    "technology": 20,
    "finance": 18,
    "healthcare": 16,
    "retail": 12,
    "education": 10,
    "other": 8,
}


def calculate_score(form_data: dict[str, Any]) -> tuple[int, dict[str, int]]:
    """Deterministic scoring based on rubric. Returns (total_score, breakdown)."""
    budget_score = BUDGET_SCORES.get(form_data.get("budget", ""), 0)
    timeline_score = TIMELINE_SCORES.get(form_data.get("timeline", ""), 0)
    industry_score = INDUSTRY_SCORES.get(form_data.get("industry", "other"), 8)
    use_case_score = min(20, len(form_data.get("use_case", "").split()) // 2)
    total = budget_score + timeline_score + industry_score + use_case_score
    breakdown = {
        "budget": budget_score,
        "timeline": timeline_score,
        "industry": industry_score,
        "use_case": use_case_score,
    }
    return min(100, total), breakdown


def qualify_lead(form_data: dict[str, Any]) -> dict[str, Any]:
    """Score lead and get LLM explanation. Score is deterministic."""
    score, breakdown = calculate_score(form_data)
    prompt = LEAD_EXPLANATION_PROMPT.format(
        score=score,
        breakdown=json.dumps(breakdown),
        company=form_data.get("company", "Unknown"),
        contact=form_data.get("contact", "Unknown"),
        industry=form_data.get("industry", "other"),
        budget=form_data.get("budget", "unknown"),
        timeline=form_data.get("timeline", "unknown"),
        use_case=form_data.get("use_case", ""),
    )
    try:
        raw = chat(prompt=prompt, system=LEAD_EXPLANATION_SYSTEM, max_tokens=512)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(match.group()) if match else {}
    except Exception as exc:
        logger.error(f"LLM explanation failed: {exc}")
        result = {}
    return {
        "score": score,
        "breakdown": breakdown,
        "explanation": result.get("explanation", f"Lead scored {score}/100."),
        "email_draft": result.get("email_draft", f"Thank you for your interest. Your score is {score}/100."),
    }
