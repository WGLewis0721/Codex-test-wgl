"""Helper utilities: PDF extraction, text chunking, markdown generation."""
from __future__ import annotations
import io
import re
from pathlib import Path
from typing import Iterator


def extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise RuntimeError("pypdf not installed; cannot extract PDF text")


def extract_text_from_file(data: bytes, filename: str) -> str:
    """Extract text from file bytes based on extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(data)
    return data.decode("utf-8", errors="replace")


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def to_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a markdown table string."""
    sep = " | ".join("---" for _ in headers)
    header_row = " | ".join(headers)
    data_rows = [" | ".join(str(c) for c in row) for row in rows]
    return "\n".join([f"| {header_row} |", f"| {sep} |"] + [f"| {r} |" for r in data_rows])


def sanitize_filename(name: str) -> str:
    """Return a safe filename by removing special characters."""
    return re.sub(r"[^\w\-_.]", "_", name)


def write_export(content: str, path: Path) -> Path:
    """Write content to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
