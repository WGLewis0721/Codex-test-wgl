"""Customer profile schema and builder."""
from __future__ import annotations
import json
import re
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.ollama import chat
from shared.logging import get_logger
from .prompts import PROFILE_SYSTEM, PROFILE_PROMPT

logger = get_logger(__name__)


def build_profile(form_data: dict[str, Any]) -> dict[str, Any]:
    """Build structured customer profile from form data using LLM."""
    prompt = PROFILE_PROMPT.format(
        company=form_data.get("company", "Unknown"),
        industry=form_data.get("industry", "Unknown"),
        team_size=form_data.get("team_size", "Unknown"),
        current_stack=form_data.get("current_stack", "Unknown"),
        pain_points=form_data.get("pain_points", ""),
        goals=form_data.get("goals", ""),
        compliance=form_data.get("compliance", "None"),
        budget=form_data.get("budget", "Unknown"),
    )
    try:
        raw = chat(prompt=prompt, system=PROFILE_SYSTEM, max_tokens=1024)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        profile = json.loads(match.group()) if match else {}
    except Exception as exc:
        logger.error(f"Profile build failed: {exc}")
        profile = {}

    return {
        "company": form_data.get("company", "Unknown"),
        "industry": form_data.get("industry", "Unknown"),
        "summary": profile.get("summary", "Profile generated."),
        "recommended_services": profile.get("recommended_services", []),
        "risk_factors": profile.get("risk_factors", []),
        "migration_complexity": profile.get("migration_complexity", "medium"),
        "priority_actions": profile.get("priority_actions", []),
        "raw_form": form_data,
    }


def profile_to_markdown(profile: dict[str, Any], version: int) -> str:
    """Convert profile to markdown summary."""
    lines = [
        f"# Customer Profile: {profile.get('company', 'Unknown')} (v{version})",
        f"\n## Summary\n{profile.get('summary', '')}",
        f"\n## Industry\n{profile.get('industry', '')}",
        "\n## Recommended Services",
    ]
    for svc in profile.get("recommended_services", []):
        lines.append(f"- {svc}")
    lines.append("\n## Risk Factors")
    for risk in profile.get("risk_factors", []):
        lines.append(f"- {risk}")
    lines.append("\n## Priority Actions")
    for action in profile.get("priority_actions", []):
        lines.append(f"- {action}")
    lines.append(f"\n**Migration Complexity:** {profile.get('migration_complexity', 'medium')}")
    return "\n".join(lines)
