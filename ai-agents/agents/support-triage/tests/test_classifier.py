"""Tests for Support Triage classifier."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from agent.classifier import deterministic_urgency


def test_critical_keywords():
    assert deterministic_urgency("Server outage affecting all users") == "critical"


def test_high_keywords():
    assert deterministic_urgency("VPN is not working for me") == "high"


def test_low_keywords():
    assert deterministic_urgency("I have a question about my account") == "low"


def test_default_medium():
    assert deterministic_urgency("I need some assistance with my setup") == "medium"


def test_case_insensitive():
    assert deterministic_urgency("SECURITY BREACH detected") == "critical"
