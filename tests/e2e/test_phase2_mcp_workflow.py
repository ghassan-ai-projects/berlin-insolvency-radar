"""End-to-end Phase 2 workflow tests through the MCP tool dispatcher."""

import tempfile
from datetime import date
from pathlib import Path

from biradar.mcp.server import call_radar_tool
from biradar.services.container import AppContainer
from biradar.services.phase2_pipeline import run_phase2_pipeline


def test_phase2_mcp_source_run_history_and_workflow_tool():
    """Verify MCP Phase 2 tool execution and source-run inspection stay local and stable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        radar_db_path = tmp_path / "phase2_mcp.duckdb"
        container = AppContainer(
            Path(__file__).parent.parent.parent / "config", radar_db_path
        )
        try:
            service_result = run_phase2_pipeline(
                start_date=date(2026, 6, 10),
                end_date=date(2026, 6, 16),
                dry_run=False,
                thread_id="phase2_mcp_service",
                db_path=radar_db_path,
                source_mode="fixture",
            )
            assert service_result["status"] == "success"

            history = call_radar_tool(
                container,
                "radar_list_source_runs",
                {"limit": 10},
            )
            assert history.ok is True
            assert len(history.data) >= 1
            assert history.data[0]["source_id"] == "official_insolvency_portal"
            source_run_id = history.data[0]["source_run_id"]

            source_audit = call_radar_tool(
                container,
                "radar_audit_trail",
                {"entity_type": "source_run", "entity_id": source_run_id, "limit": 10},
            )
            assert source_audit.ok is True
            assert any(
                event["action"] == "phase2_acquisition_completed"
                for event in source_audit.data
            )

            workflow_result = call_radar_tool(
                container,
                "radar_run_phase2_workflow",
                {
                    "start_date": "2026-06-10",
                    "end_date": "2026-06-16",
                    "dry_run": True,
                },
            )
            assert workflow_result.ok is True
            assert workflow_result.data["status"] == "success"
            assert "notify" not in (workflow_result.next_action or "").lower()
        finally:
            container.close()
