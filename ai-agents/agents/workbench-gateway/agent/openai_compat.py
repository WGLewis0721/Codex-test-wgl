"""OpenAI-compatible format conversion for Workbench Gateway."""
from __future__ import annotations
import time
import uuid
from typing import Any
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.ollama import chat, list_models
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

ALLOWED_MODELS = {
    "phi3:medium",
    "llama3.2:3b",
    "mistral:7b",
}

MAX_TOKENS_LIMIT = 4096


def get_available_models() -> list[dict[str, Any]]:
    """Return OpenAI-compatible model list."""
    ollama_models = set(list_models())
    models = []
    for model in ALLOWED_MODELS:
        if model in ollama_models:
            models.append({
                "id": model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local",
            })
    return models


def handle_chat_completion(request: dict[str, Any]) -> dict[str, Any]:
    """Process OpenAI-compatible chat completion request."""
    model = request.get("model", _settings.ollama_model)
    if model not in ALLOWED_MODELS:
        raise ValueError(f"Model '{model}' not in allowlist")

    messages = request.get("messages", [])
    max_tokens = min(request.get("max_tokens", 1024), MAX_TOKENS_LIMIT)

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    prompt = "\n".join(user_messages) if user_messages else ""

    if not prompt:
        raise ValueError("No user message provided")

    response_text = chat(prompt=prompt, model=model, system=system, max_tokens=max_tokens)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": response_text},
            "finish_reason": "stop",
        }],
        "usage": {
            # Token counts are word-split approximations, not exact tokenizer counts.
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(prompt.split()) + len(response_text.split()),
        },
    }
