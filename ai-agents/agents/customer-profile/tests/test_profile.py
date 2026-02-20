"""Tests for Customer Profile Builder."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from agent.profile import profile_to_markdown


def test_profile_to_markdown_basic():
    profile = {
        "company": "Acme Corp",
        "industry": "technology",
        "summary": "A tech company.",
        "recommended_services": ["EC2", "S3"],
        "risk_factors": ["vendor lock-in"],
        "migration_complexity": "medium",
        "priority_actions": ["audit current infra"],
    }
    md = profile_to_markdown(profile, 1)
    assert "Acme Corp" in md
    assert "v1" in md
    assert "EC2" in md
    assert "vendor lock-in" in md


def test_profile_to_markdown_empty_lists():
    profile = {
        "company": "Test Co",
        "industry": "other",
        "summary": "Summary.",
        "recommended_services": [],
        "risk_factors": [],
        "migration_complexity": "low",
        "priority_actions": [],
    }
    md = profile_to_markdown(profile, 2)
    assert "Test Co" in md
    assert "v2" in md


def test_profile_to_markdown_complexity():
    profile = {"company": "X", "industry": "finance", "summary": "s",
               "recommended_services": [], "risk_factors": [], "migration_complexity": "high", "priority_actions": []}
    md = profile_to_markdown(profile, 1)
    assert "high" in md
