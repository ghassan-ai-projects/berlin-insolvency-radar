"""E2E tests for the Phase 2 pipeline using golden fixtures."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from biradar.services.phase2_pipeline import run_phase2_pipeline


def test_phase2_pipeline_e2e_dry_run():
    """
    Test the Phase 2 pipeline end-to-end in dry-run mode.
    
    This verifies that the workflow can be constructed, initialized,
    and executed without crashing, using mock/placeholder logic.
    """
    start_date = date(2026, 6, 10)
    end_date = date(2026, 6, 16)
    
    # Use a temporary directory for any potential file writes
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override settings temporarily if needed, or rely on dry_run=True 
        # which uses in-memory DB and shouldn't touch persistent state.
        result = run_phase2_pipeline(
            start_date=start_date,
            end_date=end_date,
            dry_run=True,
            thread_id="test_e2e_thread",
        )
        
        assert result["status"] == "success"
        assert result["current_step"] == "completed"
        assert result["export_path"] is not None
        export_path = Path(result["export_path"])
        assert export_path.exists()
        export_text = export_path.read_text(encoding="utf-8")
        assert "Test Berlin GmbH" in export_text
        assert "errors" in result
        assert len(result["errors"]) == 0


def test_phase2_pipeline_quarantine_exclusion_e2e():
    """
    Verify that the E2E pipeline respects quarantine gates.
    
    If a candidate is marked as quarantined during risk review,
    it must NOT appear in the final exported JSON package.
    """
    from biradar.output.export import generate_json_package
    
    issue_data = {
        "title": "E2E Test Issue",
        "candidates": [
            {"candidate_id": "c_valid", "company_name": "Valid GmbH", "status": "publish_ready"},
            {"candidate_id": "c_quarantine", "company_name": "Quarantined UG", "status": "quarantined", "quarantine_reason": "consumer_indicator"},
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = generate_json_package(issue_data, Path(tmpdir))
        
        import json
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Assert only the valid candidate is exported
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["candidate_id"] == "c_valid"
        assert "disclaimer" in data["metadata"]
