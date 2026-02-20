"""Document management router."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.services.ingestion_service import IngestionService
from app.services.s3_service import S3Service
from app.services.vector_store import VectorStore

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

# Module-level ingestion service so the HTTP client is reused across calls.
_ingestion_svc: IngestionService | None = None


def _get_ingestion_service() -> IngestionService:
    global _ingestion_svc
    if _ingestion_svc is None:
        _ingestion_svc = IngestionService()
    return _ingestion_svc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", summary="List all ingested documents")
async def list_documents() -> dict[str, Any]:
    """Return de-duplicated document metadata stored in ChromaDB.

    Returns:
        JSON with ``documents`` list and ``total`` count.
    """
    store = VectorStore()
    docs = await asyncio.get_running_loop().run_in_executor(
        None, store.list_documents
    )
    return {"documents": docs, "total": len(docs)}


@router.post("/ingest", summary="Trigger S3 sync and re-ingest")
async def ingest_documents(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start the S3 ingestion pipeline in the background.

    The endpoint returns immediately; the actual work runs asynchronously.

    Returns:
        Acknowledgement message.
    """
    svc = _get_ingestion_service()
    background_tasks.add_task(_run_ingestion, svc)
    return {"message": "Ingestion started in the background."}


@router.get("/{doc_id}/download", summary="Generate pre-signed S3 download URL")
async def download_document(doc_id: str) -> dict[str, str]:
    """Look up the S3 key for *doc_id* and return a pre-signed URL.

    Args:
        doc_id: Stable document identifier (SHA-256 prefix of the S3 key).

    Returns:
        JSON with ``url`` field.

    Raises:
        HTTPException 404: If *doc_id* is not found in ChromaDB.
        HTTPException 502: If the pre-signed URL cannot be generated.
    """
    store = VectorStore()
    docs = await asyncio.get_running_loop().run_in_executor(None, store.list_documents)
    source_key = next(
        (d.get("source_key") for d in docs if d.get("doc_id") == doc_id), None
    )
    if not source_key:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    try:
        s3 = S3Service()
        url = await asyncio.get_running_loop().run_in_executor(
            None, lambda: s3.generate_presigned_url(source_key)
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate pre-signed URL for doc_id=%s: %s", doc_id, exc)
        raise HTTPException(status_code=502, detail="Could not generate download URL.") from exc

    return {"doc_id": doc_id, "url": url}


@router.delete("/{doc_id}", summary="Remove a document from ChromaDB")
async def delete_document(doc_id: str) -> dict[str, str]:
    """Delete all chunks associated with *doc_id* from ChromaDB.

    Args:
        doc_id: Stable document identifier.

    Returns:
        Confirmation message.

    Raises:
        HTTPException 404: If *doc_id* has no chunks in ChromaDB.
    """
    store = VectorStore()
    docs = await asyncio.get_running_loop().run_in_executor(None, store.list_documents)
    if not any(d.get("doc_id") == doc_id for d in docs):
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    await asyncio.get_running_loop().run_in_executor(
        None, lambda: store.delete_by_doc_id(doc_id)
    )
    return {"message": f"Document '{doc_id}' deleted successfully."}


# ---------------------------------------------------------------------------
# Background task helper
# ---------------------------------------------------------------------------


async def _run_ingestion(svc: IngestionService) -> None:
    """Execute the ingestion pipeline and log the summary."""
    try:
        summary = await svc.ingest_from_s3()
        logger.info("Background ingestion finished: %s", summary)
    except Exception as exc:  # noqa: BLE001
        logger.error("Background ingestion failed: %s", exc, exc_info=True)
