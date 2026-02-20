"""Tests for Workbench Gateway OpenAI compatibility."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from agent.openai_compat import ALLOWED_MODELS, MAX_TOKENS_LIMIT
from agent.limiter import is_rate_limited


def test_allowed_models_not_empty():
    assert len(ALLOWED_MODELS) > 0


def test_max_tokens_limit():
    assert MAX_TOKENS_LIMIT == 4096


def test_rate_limiter_allows_within_limit():
    client = f"test-client-{os.urandom(4).hex()}"
    for _ in range(5):
        limited = is_rate_limited(client, limit=10)
        assert not limited


def test_rate_limiter_blocks_over_limit():
    client = f"test-client-{os.urandom(4).hex()}"
    for _ in range(10):
        is_rate_limited(client, limit=10)
    assert is_rate_limited(client, limit=10)


def test_allowed_models_content():
    assert "phi3:medium" in ALLOWED_MODELS
