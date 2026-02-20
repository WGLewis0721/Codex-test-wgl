"""FastAPI server for Knowledge Copilot (RAG) agent."""
from __future__ import annotations
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from shared.schemas import HealthResponse
from shared.ollama import chat
from shared.opensearch import query_recent, summarize_events
from agent.prompts import RAG_SYSTEM, RAG_PROMPT
from agent.rag import ingest_document, retrieve, list_documents
from agent.storage import init_db, save_document, get_documents, save_query

app = FastAPI(title="Knowledge Copilot API", version="1.0.0")
init_db()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    query: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "knowledge-copilot"})


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    data = await file.read()
    result = ingest_document(data, file.filename or "unknown")
    save_document(file.filename or "unknown", result["doc_id"], result["chunks"])
    return {"filename": file.filename, "doc_id": result["doc_id"], "chunks": result["chunks"]}


@app.post("/chat", response_model=ChatResponse)
def chat_query(req: ChatRequest) -> ChatResponse:
    chunks = retrieve(req.query, top_k=req.top_k)
    if not chunks:
        return ChatResponse(answer="I don't have enough information to answer that.", sources=[], query=req.query)
    context_parts = [f"[Doc: {c['filename']}]\n{c['text']}" for c in chunks]
    context = "\n\n".join(context_parts)
    os_events = query_recent(minutes=30, top_k=3)
    os_context = summarize_events(os_events)
    if os_context:
        context = f"{context}\n\n{os_context}"
    prompt = RAG_PROMPT.format(context=context, query=req.query)
    answer = chat(prompt=prompt, system=RAG_SYSTEM, max_tokens=1024)
    sources = list({c["filename"] for c in chunks})
    save_query(req.query, answer, json.dumps(sources))
    return ChatResponse(answer=answer, sources=sources, query=req.query)


@app.get("/docs")
def list_docs() -> dict:
    docs = get_documents()
    return {"documents": docs, "total": len(docs)}
