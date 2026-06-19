import os

import pytest

from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk


def test_extraction_agent_requires_api_key():
    """Extraction should fail fast when no supported LLM API key is configured."""
    original_biradar_key = os.environ.pop("BIRADAR_LLM_API_KEY", None)
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        with pytest.raises(
            RuntimeError, match="BIRADAR_LLM_API_KEY or DEEPSEEK_API_KEY"
        ):
            extract_filing_facts("Test text", "http://example.com")
    finally:
        if original_biradar_key:
            os.environ["BIRADAR_LLM_API_KEY"] = original_biradar_key
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_risk_review_agent_requires_api_key():
    """Risk review should fail fast when no supported LLM API key is configured."""
    original_biradar_key = os.environ.pop("BIRADAR_LLM_API_KEY", None)
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)

    try:
        candidate_data = {"company_name": "Test GmbH", "status": "review_ready"}
        extraction_data = {"company_name": "Test GmbH", "legal_form": "GmbH"}
        enrichment_data = {"sector": "Tech"}
        draft_thesis = "Good opportunity."

        with pytest.raises(
            RuntimeError, match="BIRADAR_LLM_API_KEY or DEEPSEEK_API_KEY"
        ):
            review_candidate_risk(
                candidate_data, extraction_data, enrichment_data, draft_thesis
            )
    finally:
        if original_biradar_key:
            os.environ["BIRADAR_LLM_API_KEY"] = original_biradar_key
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_extraction_agent_raises_classified_runtime_error_on_model_timeout(
    monkeypatch,
):
    original_key = os.environ.get("BIRADAR_LLM_API_KEY")
    original_model = os.environ.get("BIRADAR_LLM_MODEL")
    os.environ["BIRADAR_LLM_API_KEY"] = "test-key"
    os.environ["BIRADAR_LLM_MODEL"] = "test-model"

    class FakeLLM:
        def invoke(self, *_args, **_kwargs):
            raise TimeoutError("model timed out")

    monkeypatch.setattr("biradar.agents.extraction.build_chat_llm", lambda: FakeLLM())

    try:
        with pytest.raises(RuntimeError, match="EXTRACTION_MODEL_TIMEOUT"):
            extract_filing_facts("Test text", "http://example.com")
    finally:
        if original_key is None:
            os.environ.pop("BIRADAR_LLM_API_KEY", None)
        else:
            os.environ["BIRADAR_LLM_API_KEY"] = original_key
        if original_model is None:
            os.environ.pop("BIRADAR_LLM_MODEL", None)
        else:
            os.environ["BIRADAR_LLM_MODEL"] = original_model


def test_risk_review_agent_raises_classified_runtime_error_on_model_timeout(
    monkeypatch,
):
    original_key = os.environ.get("BIRADAR_LLM_API_KEY")
    original_model = os.environ.get("BIRADAR_LLM_MODEL")
    os.environ["BIRADAR_LLM_API_KEY"] = "test-key"
    os.environ["BIRADAR_LLM_MODEL"] = "test-model"

    class FakeLLM:
        def invoke(self, *_args, **_kwargs):
            raise TimeoutError("model timed out")

    monkeypatch.setattr("biradar.agents.risk_review.build_chat_llm", lambda: FakeLLM())

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
            os.environ.pop("BIRADAR_LLM_API_KEY", None)
        else:
            os.environ["BIRADAR_LLM_API_KEY"] = original_key
        if original_model is None:
            os.environ.pop("BIRADAR_LLM_MODEL", None)
        else:
            os.environ["BIRADAR_LLM_MODEL"] = original_model
