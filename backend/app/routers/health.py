"""Health check router."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter

from app.config import settings
from app.services.s3_service import S3Service
from app.services.vector_store import VectorStore

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", summary="System health check")
async def health() -> dict:
    """Check connectivity to Ollama, ChromaDB, and S3.

    Returns:
        JSON object with ``status`` (ok/degraded) and per-component details.
    """
    results: dict = {}

    # --- Ollama ---
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=5.0) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
        results["ollama"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama health check failed: %s", exc)
        results["ollama"] = {"status": "error", "detail": str(exc)}

    # --- ChromaDB ---
    try:
        store = VectorStore()
        count = store.count()
        results["chromadb"] = {"status": "ok", "chunk_count": count}
    except Exception as exc:  # noqa: BLE001
        logger.warning("ChromaDB health check failed: %s", exc)
        results["chromadb"] = {"status": "error", "detail": str(exc)}

    # --- S3 ---
    try:
        s3 = S3Service()
        accessible = s3.check_bucket_access()
        results["s3"] = {
            "status": "ok" if accessible else "error",
            "bucket": settings.s3_bucket,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("S3 health check failed: %s", exc)
        results["s3"] = {"status": "error", "detail": str(exc)}

    overall = (
        "ok"
        if all(v.get("status") == "ok" for v in results.values())
        else "degraded"
    )
    return {"status": overall, "components": results}
