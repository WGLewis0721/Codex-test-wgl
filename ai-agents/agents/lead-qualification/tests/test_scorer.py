"""Tests for Lead Qualification scorer."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from agent.scorer import calculate_score


def test_high_budget_score():
    data = {"budget": "over_250k", "timeline": "immediately", "industry": "technology", "use_case": "enterprise platform deployment"}
    score, breakdown = calculate_score(data)
    assert score > 70
    assert breakdown["budget"] == 40


def test_low_budget_score():
    data = {"budget": "under_10k", "timeline": "no_timeline", "industry": "other", "use_case": ""}
    score, breakdown = calculate_score(data)
    assert score < 30
    assert breakdown["budget"] == 5


def test_score_max_100():
    data = {"budget": "over_250k", "timeline": "immediately", "industry": "technology",
            "use_case": " ".join(["word"] * 100)}
    score, _ = calculate_score(data)
    assert score <= 100


def test_missing_fields_default():
    score, breakdown = calculate_score({})
    assert score >= 0
    assert "budget" in breakdown


def test_deterministic():
    data = {"budget": "50k_100k", "timeline": "within_3_months", "industry": "finance", "use_case": "crm integration"}
    s1, _ = calculate_score(data)
    s2, _ = calculate_score(data)
    assert s1 == s2
