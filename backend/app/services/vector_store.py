"""ChromaDB vector store — singleton wrapper."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Singleton wrapper around a ChromaDB PersistentClient.

    All public methods are synchronous because ChromaDB's Python client is
    synchronous; callers should run them in a thread-pool executor when inside
    async routes.
    """

    _instance: VectorStore | None = None

    def __new__(cls) -> VectorStore:  # noqa: D102
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self.get_or_create_collection(
            settings.chroma_collection_name
        )
        self._initialized = True
        logger.info(
            "VectorStore initialised — collection=%s, persist_dir=%s",
            settings.chroma_collection_name,
            settings.chroma_persist_dir,
        )

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Return existing collection or create a new one.

        Args:
            name: Collection name.

        Returns:
            A ChromaDB Collection object.
        """
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert or update vectors in the collection.

        Args:
            ids: Unique identifiers for each chunk.
            embeddings: Dense float vectors.
            documents: Raw text content of each chunk.
            metadatas: Per-chunk metadata dicts.
        """
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted %d chunks into ChromaDB.", len(ids))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Query the collection for the closest chunks.

        Args:
            query_embedding: Dense query vector.
            top_k: Maximum number of results to return.

        Returns:
            List of result dicts with keys: id, document, metadata, score.
        """
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(self.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict[str, Any]] = []
        for idx in range(len(results["ids"][0])):
            output.append(
                {
                    "id": results["ids"][0][idx],
                    "document": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx],
                    # ChromaDB returns cosine *distance*; convert to similarity
                    "score": float(1.0 - results["distances"][0][idx]),
                }
            )
        return output

    def delete(self, ids: list[str]) -> None:
        """Remove chunks by ID.

        Args:
            ids: List of chunk IDs to delete.
        """
        self._collection.delete(ids=ids)
        logger.info("Deleted %d chunks from ChromaDB.", len(ids))

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Remove all chunks belonging to a document.

        Args:
            doc_id: The document identifier stored in chunk metadata.
        """
        results = self._collection.get(
            where={"doc_id": doc_id},
            include=[],
        )
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.info(
                "Deleted %d chunks for doc_id=%s from ChromaDB.", len(ids), doc_id
            )

    def list_documents(self) -> list[dict[str, Any]]:
        """Return de-duplicated document metadata from the collection.

        Returns:
            List of dicts, one per unique doc_id, containing doc-level metadata.
        """
        results = self._collection.get(include=["metadatas"])
        seen: dict[str, dict[str, Any]] = {}
        for meta in results.get("metadatas") or []:
            doc_id = meta.get("doc_id", "")
            if doc_id and doc_id not in seen:
                seen[doc_id] = meta
        return list(seen.values())

    def count(self) -> int:
        """Return the total number of chunks stored.

        Returns:
            Integer chunk count.
        """
        return self._collection.count()
