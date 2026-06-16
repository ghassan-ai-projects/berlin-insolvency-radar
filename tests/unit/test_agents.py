"""Unit tests for LLM agents (extraction and risk review)."""

import os
import pytest
from biradar.agents.extraction import extract_filing_facts
from biradar.agents.risk_review import review_candidate_risk


def test_extraction_agent_mock_fallback():
    """Test that extraction agent returns a safe mock result when no API key is present."""
    # Ensure no API key is set for this test
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)
    
    try:
        result = extract_filing_facts("Test text", "http://example.com")
        
        # Verify it returns the expected mock structure
        assert result.company_name == "Mock GmbH"
        assert result.legal_form == "GmbH"
        assert result.is_consumer_likely is False
        assert "company_name" in result.field_confidence_scores
    finally:
        # Restore original key if it existed
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key


def test_risk_review_agent_mock_fallback():
    """Test that risk review agent passes by default when no API key is present."""
    original_key = os.environ.pop("DEEPSEEK_API_KEY", None)
    
    try:
        candidate_data = {"company_name": "Test GmbH", "status": "review_ready"}
        extraction_data = {"company_name": "Test GmbH", "legal_form": "GmbH"}
        enrichment_data = {"sector": "Tech"}
        draft_thesis = "Good opportunity."
        
        result = review_candidate_risk(candidate_data, extraction_data, enrichment_data, draft_thesis)
        
        # Verify it returns a safe pass result
        assert result.passed_review is True
        assert result.confidence_in_review == 0.5
    finally:
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key
