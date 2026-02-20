"""Prompts for Customer Profile Builder."""

PROFILE_SYSTEM = """You are an expert cloud solutions architect creating structured customer profiles.
Be accurate and advisory only. Do not suggest automated infrastructure changes.
Return ONLY valid JSON matching the requested schema."""

PROFILE_PROMPT = """Build a structured customer profile from this intake information:

Company: {company}
Industry: {industry}
Team Size: {team_size}
Current Stack: {current_stack}
Pain Points: {pain_points}
Goals: {goals}
Compliance Requirements: {compliance}
Budget Range: {budget}

Return JSON with keys:
- summary (string): 2-3 sentence overview
- recommended_services (list of strings): top 3-5 relevant services
- risk_factors (list of strings): key risks to address
- migration_complexity (string): low/medium/high
- priority_actions (list of strings): top 3 next steps"""
