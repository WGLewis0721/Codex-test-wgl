"""Tests for Interview Fit analyzer."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from agent.analyzer import build_markdown_report, VALID_GRADES


def test_valid_grades_set():
    assert "A" in VALID_GRADES
    assert "F" in VALID_GRADES
    assert "X" not in VALID_GRADES


def test_build_markdown_report():
    analysis = {
        "fit_grade": "B",
        "strengths": ["Python", "FastAPI"],
        "gaps": ["Kubernetes"],
        "qa_pairs": [{"question": "Tell me about Python?", "answer": "I have 5 years experience."}],
        "study_plan": ["Study Kubernetes basics"],
    }
    md = build_markdown_report(analysis, "Senior Backend Engineer")
    assert "Grade" in md or "B" in md
    assert "Python" in md
    assert "Kubernetes" in md


def test_build_markdown_empty():
    analysis = {"fit_grade": "C", "strengths": [], "gaps": [], "qa_pairs": [], "study_plan": []}
    md = build_markdown_report(analysis, "Software Engineer")
    assert "C" in md


def test_grade_validation():
    for grade in VALID_GRADES:
        assert grade in {"A", "B", "C", "D", "F"}
