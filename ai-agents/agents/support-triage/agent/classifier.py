"""Urgency rules + LLM classifier for Support Triage."""
from __future__ import annotations
import json
import re
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from shared.ollama import chat
from shared.logging import get_logger
from .prompts import TRIAGE_SYSTEM, TRIAGE_PROMPT

logger = get_logger(__name__)

CRITICAL_KEYWORDS = {"outage", "down", "breach", "security", "emergency", "critical", "urgent"}
HIGH_KEYWORDS = {"slow", "cannot access", "error", "failed", "broken", "not working"}
LOW_KEYWORDS = {"question", "how to", "help", "info", "information", "wondering"}


def deterministic_urgency(text: str) -> str:
    """Apply keyword rules to determine initial urgency."""
    lower = text.lower()
    if any(kw in lower for kw in CRITICAL_KEYWORDS):
        return "critical"
    if any(kw in lower for kw in HIGH_KEYWORDS):
        return "high"
    if any(kw in lower for kw in LOW_KEYWORDS):
        return "low"
    return "medium"


def classify_ticket(ticket_text: str, context: str = "") -> dict[str, Any]:
    """Classify a support ticket using deterministic rules + LLM."""
    base_urgency = deterministic_urgency(ticket_text)
    prompt = TRIAGE_PROMPT.format(ticket_text=ticket_text, context=context or "none")
    try:
        raw = chat(prompt=prompt, system=TRIAGE_SYSTEM, max_tokens=512)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            result = {}
    except Exception as exc:
        logger.error(f"LLM classification failed: {exc}")
        result = {}

    return {
        "urgency": base_urgency,
        "sentiment": result.get("sentiment", "neutral"),
        "domain": result.get("domain", "other"),
        "routing": result.get("routing", "general"),
        "draft_response": result.get("draft_response", "We have received your ticket and will respond shortly."),
    }
