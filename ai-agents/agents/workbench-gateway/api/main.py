"""FastAPI OpenAI-compatible server for Workbench Gateway."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any
from shared.schemas import HealthResponse
from agent.openai_compat import handle_chat_completion, get_available_models
from agent.limiter import is_rate_limited
from agent.storage import init_db, log_request, get_recent_requests, get_stats

app = FastAPI(title="AI Workbench Gateway", version="1.0.0")
init_db()


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="phi3:medium")
    messages: list[dict[str, str]] = Field(..., min_length=1)
    max_tokens: int = Field(default=1024, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "workbench-gateway"})


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request) -> dict[str, Any]:
    client_id = request.headers.get("X-Client-ID", request.client.host if request.client else "unknown")
    if is_rate_limited(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    try:
        result = handle_chat_completion(req.model_dump())
        usage = result.get("usage", {})
        log_request(
            request_id=result["id"],
            model=req.model,
            client_id=client_id,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            status="success",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_request(
            request_id="error",
            model=req.model,
            client_id=client_id,
            prompt_tokens=0,
            completion_tokens=0,
            status="error",
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    models = get_available_models()
    return {"object": "list", "data": models}


@app.get("/dashboard")
def dashboard() -> dict[str, Any]:
    stats = get_stats()
    recent = get_recent_requests(limit=20)
    return {"stats": stats, "recent_requests": recent}
