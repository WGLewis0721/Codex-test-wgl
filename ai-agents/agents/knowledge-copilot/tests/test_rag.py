"""Tests for Knowledge Copilot RAG utilities."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.utils import chunk_text, extract_text_from_file


def test_chunk_text_basic():
    text = " ".join([f"word{i}" for i in range(100)])
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 20 for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_single_chunk():
    text = "hello world"
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == "hello world"


def test_extract_text_txt():
    data = b"Hello, world!"
    text = extract_text_from_file(data, "test.txt")
    assert "Hello" in text


def test_extract_text_md():
    data = b"# Title\n\nContent here."
    text = extract_text_from_file(data, "doc.md")
    assert "Title" in text
