"""Chat router — RAG-powered conversation endpoint."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.services.ingestion_service import IngestionService
from app.services.vector_store import VectorStore

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session history
# ---------------------------------------------------------------------------

# session_id → deque of {"role": str, "content": str}
_sessions: dict[str, deque[dict[str, str]]] = {}
_MAX_HISTORY = 20
# Maximum number of concurrent sessions kept in memory to prevent unbounded growth.
_MAX_SESSIONS = 1_000

_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert ITSM Tier 1 support agent. Your role is to help users resolve \
IT issues quickly and accurately.

Use the following retrieved knowledge-base excerpts to answer the user's question. \
If the context does not contain relevant information, say so and provide a best-effort \
answer based on general IT knowledge.

--- CONTEXT START ---
{context}
--- CONTEXT END ---

Guidelines:
- Be concise, professional, and empathetic.
- Provide step-by-step instructions when applicable.
- If you cannot resolve the issue, advise the user on escalation paths.
- Never fabricate ticket numbers, names, or system states.
"""

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Incoming chat request payload."""

    session_id: str
    message: str
    model: str | None = None


class SourceDoc(BaseModel):
    """Metadata for a single retrieved source chunk."""

    doc_id: str
    chunk_id: str
    score: float
    preview: str


class ChatResponse(BaseModel):
    """Chat endpoint response payload."""

    response: str
    sources: list[SourceDoc]
    session_id: str


# ---------------------------------------------------------------------------
# Module-level shared resources
# ---------------------------------------------------------------------------

_ingestion_svc: IngestionService | None = None


def _get_ingestion_service() -> IngestionService:
    global _ingestion_svc
    if _ingestion_svc is None:
        _ingestion_svc = IngestionService()
    return _ingestion_svc


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _get_or_create_session(session_id: str) -> deque[dict[str, str]]:
    """Return the history deque for *session_id*, creating it if necessary.

    When the maximum number of tracked sessions is reached the oldest session
    (by insertion order, Python 3.7+ dict guarantee) is evicted to prevent
    unbounded memory growth.

    Args:
        session_id: Caller-supplied session identifier.

    Returns:
        Mutable deque capped at :data:`_MAX_HISTORY` messages.
    """
    if session_id not in _sessions:
        if len(_sessions) >= _MAX_SESSIONS:
            # Evict the oldest session
            oldest = next(iter(_sessions))
            del _sessions[oldest]
            logger.debug("Evicted oldest session %s (session cap=%d).", oldest, _MAX_SESSIONS)
        _sessions[session_id] = deque(maxlen=_MAX_HISTORY)
    return _sessions[session_id]



@router.post("/chat", response_model=ChatResponse, summary="RAG chat with ITSM agent")
async def chat(req: ChatRequest) -> ChatResponse:
    """Handle a user message with retrieval-augmented generation.

    Steps:
    1. Embed the user's message via Ollama.
    2. Retrieve the top-K most relevant chunks from ChromaDB.
    3. Build a system prompt that includes the retrieved context.
    4. Send the full conversation history + system prompt to Ollama ``/api/chat``.
    5. Persist the exchange in the in-memory session history.

    Args:
        req: Chat request with ``session_id``, ``message``, and optional ``model``.

    Returns:
        :class:`ChatResponse` containing the assistant reply and source docs.

    Raises:
        HTTPException 502: If the Ollama service is unreachable.
    """
    svc = _get_ingestion_service()
    model = req.model or settings.chat_model

    # 1. Embed the query
    try:
        query_embedding = await _embed_with_retry(svc, req.message)
    except httpx.HTTPError as exc:
        logger.error("Embedding call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Embedding service unavailable.") from exc

    # 2. Retrieve relevant chunks
    store = VectorStore()
    raw_results = await asyncio.get_running_loop().run_in_executor(
        None,
        lambda: store.search(query_embedding, top_k=settings.top_k_results),
    )

    sources: list[SourceDoc] = []
    context_parts: list[str] = []
    for hit in raw_results:
        meta = hit.get("metadata", {})
        preview = hit["document"][:300]
        sources.append(
            SourceDoc(
                doc_id=meta.get("doc_id", ""),
                chunk_id=meta.get("chunk_id", hit["id"]),
                score=round(hit["score"], 4),
                preview=preview,
            )
        )
        context_parts.append(
            f"[Source: {meta.get('source_key', 'unknown')}]\n{hit['document']}"
        )

    context = "\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # 3. Build message list
    system_message = {
        "role": "system",
        "content": _SYSTEM_PROMPT_TEMPLATE.format(context=context),
    }

    history = _get_or_create_session(req.session_id)
    history.append({"role": "user", "content": req.message})

    messages = [system_message] + list(history)

    # 4. Call Ollama /api/chat
    try:
        assistant_content = await _chat_with_retry(messages, model)
    except httpx.HTTPError as exc:
        logger.error("Ollama chat call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Chat service unavailable.") from exc

    # 5. Store assistant turn
    history.append({"role": "assistant", "content": assistant_content})

    return ChatResponse(
        response=assistant_content,
        sources=sources,
        session_id=req.session_id,
    )


# ---------------------------------------------------------------------------
# Ollama helpers with retry
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _embed_with_retry(svc: IngestionService, text: str) -> list[float]:
    """Embed *text* using the shared IngestionService HTTP client."""
    return await svc.embed(text)


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _chat_with_retry(
    messages: list[dict[str, Any]],
    model: str,
) -> str:
    """Send *messages* to Ollama and return the assistant's reply text.

    Streaming is consumed and concatenated into a single string so that the
    JSON response schema remains simple. Streaming can be exposed to clients
    via Server-Sent Events in a future iteration.

    Args:
        messages: Full conversation including system message.
        model: Ollama model tag.

    Returns:
        Complete assistant response string.

    Raises:
        httpx.HTTPError: On transport or HTTP-level errors.
    """
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url, timeout=120.0
    ) as client:
        response = await client.post(
            "/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
