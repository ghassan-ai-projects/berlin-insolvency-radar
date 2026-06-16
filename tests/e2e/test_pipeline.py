"""E2E tests for the workflow pipeline using golden fixtures."""

import json
import tempfile
from datetime import date
from pathlib import Path

from biradar.services.pipeline import (
    _stub_enricher,
    _stub_extractor,
    _stub_risk_reviewer,
    run_pipeline,
    run_pipeline_check,
)


def test_pipeline_e2e_dry_run():
    start_date = date(2026, 6, 10)
    end_date = date(2026, 6, 16)

    with tempfile.TemporaryDirectory():
        result = run_pipeline(
            start_date=start_date,
            end_date=end_date,
            dry_run=True,
            thread_id="test_e2e_thread",
            extractor=_stub_extractor,
            risk_reviewer=_stub_risk_reviewer,
            enricher=_stub_enricher,
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
        assert len(result["errors"]) == 0


def test_pipeline_quarantine_exclusion_e2e():
    from biradar.output.export import generate_json_package

    issue_data = {
        "title": "E2E Test Issue",
        "candidates": [
            {
                "candidate_id": "c_valid",
                "company_name": "Valid GmbH",
                "status": "publish_ready",
            },
            {
                "candidate_id": "c_quarantine",
                "company_name": "Quarantined UG",
                "status": "quarantined",
                "quarantine_reason": "consumer_indicator",
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = generate_json_package(issue_data, Path(tmpdir))
        with open(export_path, encoding="utf-8") as handle:
            data = json.load(handle)

    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["candidate_id"] == "c_valid"
    assert "disclaimer" in data["metadata"]


def test_pipeline_fixture_mode_persists_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "workflow_fixture.duckdb"
        result = run_pipeline(
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 16),
            dry_run=False,
            thread_id="fixture_persist_test",
            db_path=db_path,
            source_mode="fixture",
            extractor=_stub_extractor,
            risk_reviewer=_stub_risk_reviewer,
            enricher=_stub_enricher,
        )
        assert result["status"] == "success"
        assert result["issue_id"] is not None

        from biradar.storage.db import Database

        db = Database(db_path)
        try:
            assert (
                db.conn.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0] == 1
            )
            assert (
                db.conn.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0] == 1
            )
            assert (
                db.conn.execute(
                    "SELECT COUNT(*) FROM candidates WHERE status = 'publish_ready'"
                ).fetchone()[0]
                == 1
            )
            assert db.conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 1
        finally:
            db.close()

        export_path = Path(result["export_path"])
        json_candidates = sorted(export_path.parent.glob("issue_data_*.json"))
        assert json_candidates, "Expected a JSON export artifact"
        data = json.loads(json_candidates[-1].read_text(encoding="utf-8"))
        assert "audit_summary" in data["metadata"]
        assert data["metadata"]["audit_summary"]["publish_ready_candidates"] == 1
        assert "content_sections" in data["candidates"][0]
        assert "facts" in data["candidates"][0]["content_sections"]
        assert "editorial" in data["candidates"][0]["content_sections"]


def test_pipeline_check_command_path_passes():
    result = run_pipeline_check()
    assert result["status"] == "success"
    assert result["counts"]["source_runs"] == 2
    assert result["counts"]["raw_records"] == 1
    assert result["counts"]["candidates"] == 1
    assert result["counts"]["publish_ready"] == 1
    assert result["counts"]["issues"] == 1  # second run skips already-processed records
