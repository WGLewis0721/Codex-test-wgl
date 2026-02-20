"""Document ingestion pipeline: S3 → parse → chunk → embed → ChromaDB."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.services.s3_service import S3Service
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates the full document ingestion pipeline.

    The pipeline stages are:
    1. List objects in S3 via :class:`~app.services.s3_service.S3Service`.
    2. Download each object to a temporary file.
    3. Parse text from PDF, Markdown, or plain-text content.
    4. Chunk the text with a sliding window and configurable overlap.
    5. Generate embeddings via Ollama.
    6. Upsert embeddings + metadata into ChromaDB.
    """

    def __init__(self) -> None:
        self._s3 = S3Service()
        self._store = VectorStore()
        self._http = httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=120.0)

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    async def ingest_from_s3(self) -> dict[str, Any]:
        """Run the full S3 ingestion pipeline.

        Returns:
            Summary dict with ``ingested``, ``skipped``, and ``errors`` counts.
        """
        documents = await asyncio.get_running_loop().run_in_executor(
            None, self._s3.list_documents
        )
        logger.info("Starting ingestion of %d documents from S3.", len(documents))

        ingested = 0
        skipped = 0
        errors = 0

        for doc_meta in documents:
            key: str = doc_meta["key"]
            content_type: str = doc_meta["content_type"]
            local_path: Path | None = None

            try:
                local_path, _ = await asyncio.get_running_loop().run_in_executor(
                    None, self._s3.download_document, key
                )
                text = await asyncio.get_running_loop().run_in_executor(
                    None, self.parse_document, local_path, content_type
                )
                if not text.strip():
                    logger.warning("Empty text extracted from key=%s, skipping.", key)
                    skipped += 1
                    continue

                doc_id = _stable_doc_id(key)
                chunks = self.chunk_text(text, doc_id, source_key=key)
                await self.embed_and_store(chunks)
                ingested += 1
                logger.info("Ingested key=%s (%d chunks).", key, len(chunks))

            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to ingest key=%s: %s", key, exc, exc_info=True)
                errors += 1
            finally:
                if local_path and local_path.exists():
                    local_path.unlink(missing_ok=True)

        summary = {"ingested": ingested, "skipped": skipped, "errors": errors}
        logger.info("Ingestion complete: %s", summary)
        return summary

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse_document(self, path: Path, content_type: str) -> str:
        """Extract plain text from a document file.

        Args:
            path: Local filesystem path to the file.
            content_type: MIME type used to select the parsing strategy.

        Returns:
            Extracted plain-text string.
        """
        if content_type == "application/pdf":
            return self._parse_pdf(path)
        if content_type in {"text/markdown"}:
            return self._parse_markdown(path)
        # Default: plain text
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _parse_pdf(path: Path) -> str:
        """Extract text from all pages of a PDF."""
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    @staticmethod
    def _parse_markdown(path: Path) -> str:
        """Strip Markdown syntax and return readable text."""
        raw = path.read_text(encoding="utf-8", errors="replace")
        # Remove fenced code blocks
        raw = re.sub(r"```[\s\S]*?```", "", raw)
        # Remove inline code
        raw = re.sub(r"`[^`]*`", "", raw)
        # Remove headings markers
        raw = re.sub(r"#{1,6}\s+", "", raw)
        # Remove bold/italic markers
        raw = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", raw)
        raw = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", raw)
        # Remove links, keep text
        raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw)
        # Remove images
        raw = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", raw)
        # Collapse excess whitespace
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        source_key: str = "",
    ) -> list[dict[str, Any]]:
        """Split *text* into overlapping chunks with metadata.

        Args:
            text: Full document text.
            doc_id: Stable document identifier (used in ChromaDB metadata).
            source_key: Original S3 object key stored for traceability.

        Returns:
            List of chunk dicts with keys: chunk_id, text, metadata.
        """
        size = settings.chunk_size
        overlap = settings.chunk_overlap
        words = text.split()
        chunks: list[dict[str, Any]] = []

        start = 0
        index = 0
        while start < len(words):
            end = min(start + size, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_id = f"{doc_id}_chunk_{index}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "doc_id": doc_id,
                        "chunk_id": chunk_id,
                        "source_key": source_key,
                        "chunk_index": index,
                        "total_chunks": 0,  # back-filled below
                    },
                }
            )
            index += 1
            if end == len(words):
                break
            start += size - overlap

        # Back-fill total_chunks now that we know the final count
        total = len(chunks)
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = total

        return chunks

    # ------------------------------------------------------------------
    # Embedding & storage
    # ------------------------------------------------------------------

    async def embed_and_store(self, chunks: list[dict[str, Any]]) -> None:
        """Generate embeddings for *chunks* and upsert them into ChromaDB.

        Args:
            chunks: List of chunk dicts as returned by :meth:`chunk_text`.
        """
        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            embedding = await self.embed(chunk["text"])
            ids.append(chunk["chunk_id"])
            embeddings.append(embedding)
            documents.append(chunk["text"])
            metadatas.append(chunk["metadata"])

        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._store.upsert(ids, embeddings, documents, metadatas),
        )

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def embed(self, text: str) -> list[float]:
        """Call Ollama's embeddings endpoint with retry logic.

        Args:
            text: Text to embed.

        Returns:
            Dense float vector.

        Raises:
            httpx.HTTPError: After all retry attempts are exhausted.
        """
        response = await self._http.post(
            "/api/embeddings",
            json={"model": settings.embed_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._http.aclose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_doc_id(s3_key: str) -> str:
    """Derive a short, stable identifier from an S3 key.

    Args:
        s3_key: S3 object key string.

    Returns:
        Hex string suitable for use as a ChromaDB metadata value.
    """
    return hashlib.sha256(s3_key.encode()).hexdigest()[:16]
