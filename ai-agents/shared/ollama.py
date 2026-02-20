"""Ollama client wrapper."""
from __future__ import annotations
import httpx
from typing import Any
from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

ALLOWED_MODELS = {
    "phi3:medium",
    "llama3.2:3b",
    "nomic-embed-text",
    "mistral:7b",
}


def validate_model(model: str) -> str:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"Model '{model}' not in allowlist: {ALLOWED_MODELS}")
    return model


def chat(
    prompt: str,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send a chat completion request to Ollama."""
    model = model or _settings.ollama_model
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"num_predict": max_tokens},
        "stream": False,
    }
    try:
        resp = httpx.post(
            f"{_settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as exc:
        logger.error(f"Ollama chat error: {exc}")
        raise


def embed(text: str, model: str | None = None) -> list[float]:
    """Generate text embeddings."""
    model = model or _settings.ollama_embed_model
    try:
        resp = httpx.post(
            f"{_settings.ollama_base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as exc:
        logger.error(f"Ollama embed error: {exc}")
        raise


def list_models() -> list[str]:
    """List available models from Ollama."""
    try:
        resp = httpx.get(
            f"{_settings.ollama_base_url}/api/tags",
            timeout=10.0,
        )
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []
