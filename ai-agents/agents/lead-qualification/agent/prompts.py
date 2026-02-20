"""Prompts for Lead Qualification agent."""

LEAD_EXPLANATION_SYSTEM = """You are a sales expert explaining lead qualification scores.
Be concise, professional, and avoid making compliance claims.
Return ONLY valid JSON."""

LEAD_EXPLANATION_PROMPT = """A lead received a score of {score}/100 with this breakdown:
{breakdown}

Company: {company}
Contact: {contact}
Industry: {industry}
Budget: {budget}
Timeline: {timeline}
Use case: {use_case}

Provide:
1. A 2-3 sentence explanation of the score
2. A professional follow-up email draft

Return JSON with keys: explanation, email_draft"""
