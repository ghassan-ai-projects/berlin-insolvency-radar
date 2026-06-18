"""Unit tests for LLM agents (extraction and risk review)."""

import os

import pytest

from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk


def test_extraction_agent_requires_api_key():
    """Extraction should fail fast when the API key is missing."""
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            extract_filing_facts("Test text", "http://example.com")
    finally:
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_risk_review_agent_requires_api_key():
    """Risk review should fail fast when the API key is missing."""
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        candidate_data = {"company_name": "Test GmbH", "status": "review_ready"}
        extraction_data = {"company_name": "Test GmbH", "legal_form": "GmbH"}
        enrichment_data = {"sector": "Tech"}
        draft_thesis = "Good opportunity."

        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            review_candidate_risk(
                candidate_data, extraction_data, enrichment_data, draft_thesis
            )
    finally:
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_extraction_agent_raises_classified_runtime_error_on_model_timeout(
    monkeypatch,
):
    original_key = os.environ.get("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = "test-key"

    class FakeChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, *_args, **_kwargs):
            raise TimeoutError("model timed out")

    monkeypatch.setattr("biradar.agents.extraction.ChatOpenAI", FakeChatOpenAI)

    try:
        with pytest.raises(RuntimeError, match="EXTRACTION_MODEL_TIMEOUT"):
            extract_filing_facts("Test text", "http://example.com")
    finally:
        if original_key is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_risk_review_agent_raises_classified_runtime_error_on_model_timeout(
    monkeypatch,
):
    original_key = os.environ.get("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = "test-key"

    class FakeChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, *_args, **_kwargs):
            raise TimeoutError("model timed out")

    monkeypatch.setattr("biradar.agents.risk_review.ChatOpenAI", FakeChatOpenAI)

    try:
        with pytest.raises(RuntimeError, match="RISK_REVIEW_MODEL_TIMEOUT"):
            review_candidate_risk(
                {"company_name": "Test GmbH", "status": "review_ready"},
                {"company_name": "Test GmbH", "legal_form": "GmbH"},
                {"sector": "Tech"},
                "Good opportunity.",
            )
    finally:
        if original_key is None:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        else:
            os.environ["DEEPSEEK_API_KEY"] = original_key
