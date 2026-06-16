"""E2E tests for the Phase 2 pipeline using golden fixtures."""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from biradar.services.phase2_pipeline import run_phase2_check, run_phase2_pipeline


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
        assert "## Disclaimer" in export_text
        assert "## Run Summary" in export_text
        assert "**Facts:**" in export_text
        assert "**Editorial Context:**" in export_text
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


def test_phase2_pipeline_fixture_mode_persists_state():
    """Fixture-backed non-dry-run should persist source runs, candidates, and issue exports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "phase2_fixture.duckdb"
        result = run_phase2_pipeline(
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 16),
            dry_run=False,
            thread_id="fixture_persist_test",
            db_path=db_path,
            source_mode="fixture",
        )
        assert result["status"] == "success"
        assert result["issue_id"] is not None

        from biradar.storage.db import Database

        db = Database(db_path)
        try:
            assert db.conn.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0] == 1
            assert db.conn.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 1
            assert db.conn.execute("SELECT COUNT(*) FROM candidates WHERE status = 'publish_ready'").fetchone()[0] == 1
            assert db.conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 1
        finally:
            db.close()
        json_path = Path(result["export_path"].replace("issue_draft_", "issue_data_").replace(".md", ".json"))
        assert json_path.exists()
        import json
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "audit_summary" in data["metadata"]
        assert data["metadata"]["audit_summary"]["publish_ready_candidates"] == 1
        assert "content_sections" in data["candidates"][0]
        assert "facts" in data["candidates"][0]["content_sections"]
        assert "editorial" in data["candidates"][0]["content_sections"]


def test_phase2_check_command_path_passes():
    """The local fixture-backed phase2-check helper should pass end to end."""
    result = run_phase2_check()
    assert result["status"] == "success"
    assert result["counts"]["source_runs"] == 2
    assert result["counts"]["raw_records"] == 1
    assert result["counts"]["candidates"] == 1
    assert result["counts"]["publish_ready"] == 1
    assert result["counts"]["issues"] == 2
