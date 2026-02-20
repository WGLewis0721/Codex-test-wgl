"""FastAPI server for Lead Qualification agent."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from fastapi import FastAPI
from pydantic import BaseModel, Field
from shared.schemas import HealthResponse, PaginatedResponse
from agent.scorer import qualify_lead
from agent.storage import init_db, save_lead, get_history, count_all

app = FastAPI(title="Lead Qualification API", version="1.0.0")
init_db()


class LeadFormData(BaseModel):
    company: str = Field(..., min_length=1, max_length=200)
    contact: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(default="other")
    budget: str = Field(default="under_10k")
    timeline: str = Field(default="no_timeline")
    use_case: str = Field(default="", max_length=1000)


class LeadResponse(BaseModel):
    score: int
    breakdown: dict
    explanation: str
    email_draft: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "lead-qualification"})


@app.post("/score", response_model=LeadResponse)
def score(form_data: LeadFormData) -> LeadResponse:
    result = qualify_lead(form_data.model_dump())
    save_lead(form_data.model_dump(), result)
    return LeadResponse(**result)


@app.get("/history", response_model=PaginatedResponse)
def history(limit: int = 20, offset: int = 0) -> PaginatedResponse:
    items = get_history(limit=limit, offset=offset)
    total = count_all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
