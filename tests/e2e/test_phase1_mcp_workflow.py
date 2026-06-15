"""End-to-end Phase 1 workflow test through the MCP tool dispatcher."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from biradar.mcp.server import call_radar_tool
from biradar.services.container import AppContainer
from tests.fixtures.phase1.build_legacy_fixture import build_legacy_fixture


@pytest.fixture
def config_dir():
    return Path(__file__).parent.parent.parent / "config"


def test_phase1_editorial_workflow_runs_end_to_end(config_dir):
    """Run the complete fixture-backed Phase 1 product workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        radar_db_path = tmp_path / "radar_e2e.duckdb"
        legacy_db_path = tmp_path / "legacy_fixture.duckdb"
        fixture_dir = Path(__file__).parent.parent / "fixtures" / "phase1"
        build_legacy_fixture(
            str(fixture_dir / "fixture_rows.json"), str(legacy_db_path)
        )

        container = AppContainer(config_dir, radar_db_path)
        try:
            health = call_radar_tool(container, "radar_health", {})
            assert health.ok is True
            assert health.data["database"]["connected"] is True
            assert health.data["counts"] == {}

            dry_run = call_radar_tool(
                container,
                "radar_import_legacy_scout",
                {
                    "legacy_db_path": str(legacy_db_path),
                    "actor": "e2e_agent",
                },
            )
            assert dry_run.ok is True
            assert dry_run.data["dry_run"] is True
            assert dry_run.data["raw_records_seen"] == 8
            assert dry_run.data["distinct_candidates"] == 5
            assert dry_run.data["duplicates"] == 1
            assert dry_run.data["rejected"] == 2
            assert dry_run.audit_id is None

            real_import = call_radar_tool(
                container,
                "radar_import_legacy_scout",
                {
                    "legacy_db_path": str(legacy_db_path),
                    "dry_run": False,
                    "actor": "e2e_agent",
                },
            )
            assert real_import.ok is True
            assert real_import.data["dry_run"] is False
            assert real_import.data["distinct_candidates"] == 5
            assert real_import.audit_id is not None

            queue = call_radar_tool(container, "radar_list_candidates", {})
            assert queue.ok is True
            review_ready = [
                candidate
                for candidate in queue.data
                if candidate["status"] == "review_ready"
                and candidate["evidence_count"] > 0
            ]
            assert len(review_ready) >= 2

            approved_candidate = review_ready[0]
            unapproved_candidate = review_ready[1]
            detail = call_radar_tool(
                container,
                "radar_get_candidate",
                {"candidate_id": approved_candidate["candidate_id"]},
            )
            assert detail.ok is True
            assert (
                detail.data["candidate"]["candidate_id"]
                == approved_candidate["candidate_id"]
            )
            assert detail.data["evidence"]
            assert detail.data["source_lineage"]
            assert "audit_events" in detail.data

            review = call_radar_tool(
                container,
                "radar_review_candidate",
                {
                    "candidate_id": approved_candidate["candidate_id"],
                    "decision": "approve",
                    "reviewer": "e2e_reviewer",
                    "note": "E2E approval for local workflow verification.",
                    "score_input": {
                        "company_value": 4,
                        "asset_quality": 4,
                        "sector_attractiveness": 3,
                        "speed_of_action": 4,
                        "legal_risk": 2,
                        "rationale": {
                            "company_value": "Representative fixture candidate."
                        },
                    },
                },
            )
            assert review.ok is True
            assert review.data["status"] == "publish_ready"
            assert review.data["score_id"] is not None
            assert review.audit_id is not None

            draft = call_radar_tool(
                container,
                "radar_create_issue_draft",
                {
                    "week": "2026-W25",
                    "tier": "free",
                    "candidate_ids": [
                        unapproved_candidate["candidate_id"],
                        approved_candidate["candidate_id"],
                    ],
                    "title": "E2E Berlin Insolvency Radar",
                    "actor": "e2e_agent",
                },
            )
            assert draft.ok is True
            assert draft.data["candidate_count"] == 1
            assert draft.audit_id is not None
            assert any("not publish_ready" in warning for warning in draft.warnings)
            issue_id = draft.data["issue_id"]

            exported = call_radar_tool(
                container,
                "radar_export_issue",
                {
                    "issue_id": issue_id,
                    "format": "markdown",
                    "actor": "e2e_agent",
                },
            )
            assert exported.ok is True
            export_path = Path(exported.data["path"])
            assert export_path.exists()
            assert export_path.parent == radar_db_path.parent / "exports"
            assert exported.data["sha256"].startswith("sha256:")
            assert "beehiiv" not in (exported.next_action or "").lower()

            exported_markdown = export_path.read_text(encoding="utf-8")
            assert "# E2E Berlin Insolvency Radar" in exported_markdown
            assert approved_candidate["canonical_company_name"] in exported_markdown
            assert (
                unapproved_candidate["canonical_company_name"] not in exported_markdown
            )
            assert "Disclaimer" in exported_markdown

            candidate_audit = call_radar_tool(
                container,
                "radar_audit_trail",
                {
                    "entity_type": "candidate",
                    "entity_id": approved_candidate["candidate_id"],
                    "limit": 20,
                },
            )
            assert candidate_audit.ok is True
            assert "candidate_reviewed" in [
                event["action"] for event in candidate_audit.data
            ]

            issue_audit = call_radar_tool(
                container,
                "radar_audit_trail",
                {"entity_type": "issue", "entity_id": issue_id, "limit": 20},
            )
            assert issue_audit.ok is True
            issue_actions = [event["action"] for event in issue_audit.data]
            assert "issue_draft_created" in issue_actions
            assert "issue_exported" in issue_actions

            final_health = call_radar_tool(container, "radar_health", {})
            assert final_health.ok is True
            assert final_health.data["counts"]["publish_ready"] == 1
            assert final_health.data["last_successful_source_run"] is not None
        finally:
            container.close()
