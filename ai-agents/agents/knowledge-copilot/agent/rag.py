"""RAG pipeline: chunking, embedding, retrieval using ChromaDB."""
from __future__ import annotations
import hashlib
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.ollama import embed
from shared.utils import extract_text_from_file, chunk_text
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_chroma_client():
    import chromadb
    persist_dir = os.path.join(_settings.sqlite_dir, "chroma")
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def _get_collection():
    client = _get_chroma_client()
    return client.get_or_create_collection("knowledge_base")


def ingest_document(data: bytes, filename: str) -> dict[str, int]:
    """Chunk, embed, and store a document. Returns chunk count."""
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(data)} bytes (max {MAX_FILE_SIZE})")
    text = extract_text_from_file(data, filename)
    chunks = chunk_text(text, chunk_size=400, overlap=40)
    collection = _get_collection()
    doc_id = hashlib.sha256(data).hexdigest()[:16]
    ids, docs, metas, embs = [], [], [], []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_{i}"
        emb = embed(chunk)
        ids.append(chunk_id)
        docs.append(chunk)
        metas.append({"filename": filename, "chunk_idx": i, "doc_id": doc_id})
        embs.append(emb)
    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    return {"doc_id": doc_id, "chunks": len(chunks)}


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve top-k relevant chunks for a query."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    q_emb = embed(query)
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    items = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        items.append({"text": doc, "filename": meta.get("filename", "unknown"), "distance": dist})
    return items


def list_documents() -> list[str]:
    """List unique document filenames in the collection."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    results = collection.get(include=["metadatas"])
    seen = set()
    filenames = []
    for meta in results["metadatas"]:
        fn = meta.get("filename", "unknown")
        if fn not in seen:
            seen.add(fn)
            filenames.append(fn)
    return sorted(filenames)
