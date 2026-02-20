"""FastAPI server for Support Triage agent."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.schemas import HealthResponse, PaginatedResponse
from shared.opensearch import query_recent, summarize_events
from agent.classifier import classify_ticket
from agent.storage import init_db, save_analysis, get_history, count_all

app = FastAPI(title="Support Triage API", version="1.0.0")

init_db()


class TicketRequest(BaseModel):
    ticket_text: str = Field(..., min_length=1, max_length=5000)


class AnalysisResponse(BaseModel):
    urgency: str
    sentiment: str
    domain: str
    routing: str
    draft_response: str
    ticket_text: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "support-triage"})


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(req: TicketRequest) -> AnalysisResponse:
    events = query_recent(minutes=30, top_k=5)
    context = summarize_events(events)
    result = classify_ticket(req.ticket_text, context=context)
    save_analysis(
        ticket_text=req.ticket_text,
        urgency=result["urgency"],
        sentiment=result["sentiment"],
        domain=result["domain"],
        routing=result["routing"],
        draft_response=result["draft_response"],
    )
    return AnalysisResponse(ticket_text=req.ticket_text, **result)


@app.get("/history", response_model=PaginatedResponse)
def history(limit: int = 20, offset: int = 0) -> PaginatedResponse:
    items = get_history(limit=limit, offset=offset)
    total = count_all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
