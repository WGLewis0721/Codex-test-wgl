"""Prompts for Interview Fit agent."""

FIT_SYSTEM = """You are an expert career coach and recruiter. Analyze resumes against job descriptions.
Be objective and factual. Do not invent company facts or hallucinate credentials.
Do not store or log any PII beyond what is necessary. Return ONLY valid JSON."""

FIT_PROMPT = """Analyze this candidate's fit for the position.

Resume:
{resume_text}

Job Description:
{jd_text}

Provide a comprehensive analysis as JSON with these exact keys:
- fit_grade: letter grade A through F
- strengths: list of 3-5 key strengths matching the JD
- gaps: list of 3-5 skill/experience gaps
- qa_pairs: list of 10 objects with 'question' and 'answer' keys for interview prep
- study_plan: list of 5 study topics with brief descriptions"""
