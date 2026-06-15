"""Phase 0 Acceptance Tests for Foundation and Skeleton."""

import json
import tempfile
from pathlib import Path

import pytest

from biradar.config.settings import load_config
from biradar.graph.phase0_workflow import build_phase0_health_workflow
from biradar.mcp.server import call_radar_tool, create_mcp_server, list_radar_tools
from biradar.services.container import AppContainer
from biradar.storage.db import Database


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "radar_test.duckdb"


@pytest.fixture
def config_dir():
    return Path(__file__).parent.parent.parent / "config"


@pytest.fixture
def container(temp_db_path, config_dir):
    # Create clean config if needed, but we use the real one for structure
    container = AppContainer(config_dir, temp_db_path)
    yield container
    container.close()


def test_at_0_1_fresh_database_boot(config_dir, temp_db_path):
    """AT-0.1: Fresh Database Boot creates expected schema."""
    db = Database(temp_db_path)
    db.run_migrations()

    # Check core tables exist
    tables = db.conn.execute("SHOW TABLES").fetchall()
    table_names = [row[0] for row in tables]

    expected_tables = [
        "schema_migrations",
        "source_providers",
        "source_runs",
        "raw_records",
        "candidates",
        "candidate_sources",
        "evidence_items",
        "scores",
        "reviews",
        "issues",
        "issue_candidates",
        "audit_events",
    ]
    for tbl in expected_tables:
        assert tbl in table_names, f"Table {tbl} not found"
    db.close()


def test_at_0_2_health_tool_works_on_fresh_db(container):
    """AT-0.2: Health Tool Works On Fresh DB."""
    result = call_radar_tool(container, "radar_health", {})
    assert result.ok is True
    assert result.data["database"]["connected"] is True
    assert result.data["database"]["schema_version"] == "002_audit_table"
    assert result.data["counts"] == {}  # Empty on fresh DB
    assert "next_action" in result.data


def test_at_0_3_result_envelope_is_stable(container):
    """AT-0.3: Result Envelope Is Stable."""
    tools = list_radar_tools()
    assert [tool.name for tool in tools] == [
        "radar_health",
        "radar_import_legacy_scout",
        "radar_list_candidates",
        "radar_get_candidate",
        "radar_review_candidate",
        "radar_create_issue_draft",
        "radar_export_issue",
        "radar_audit_trail",
    ]

    # Test success envelope
    health_result = call_radar_tool(container, "radar_health", {})
    assert hasattr(health_result, "ok")
    assert hasattr(health_result, "data")
    assert hasattr(health_result, "warnings")
    assert hasattr(health_result, "errors")
    assert hasattr(health_result, "next_action")

    # Test failure envelope
    candidate_result = call_radar_tool(container, "radar_get_candidate", {})
    assert candidate_result.ok is False
    assert len(candidate_result.errors) > 0
    assert candidate_result.errors[0]["code"] == "VALIDATION_ERROR"
    assert "message" in candidate_result.errors[0]
    assert candidate_result.errors[0]["retryable"] is False
    assert "next_action" in candidate_result.errors[0]


def test_at_0_3_mcp_server_constructs(config_dir, temp_db_path):
    """AT-0.3: MCP server can be constructed and handlers serialize envelopes."""
    server = create_mcp_server(config_dir, temp_db_path)
    assert server.name == "biradar"

    container = AppContainer(config_dir, temp_db_path)
    try:
        result = call_radar_tool(container, "radar_health", {})
        payload = json.loads(json.dumps(result.model_dump(), default=str))
        assert payload["ok"] is True
        assert set(payload.keys()) >= {
            "ok",
            "data",
            "warnings",
            "errors",
            "audit_id",
            "next_action",
        }
    finally:
        container.close()


def test_at_0_4_audit_event_can_be_written_and_read(container):
    """AT-0.4: Audit Event Can Be Written And Read."""
    audit_id = container.audit_repo.log_event(
        actor="test_user",
        action="test_action",
        entity_type="test_entity",
        entity_id="test_123",
        request_data={"foo": "bar"},
        result_data={"status": "success"},
    )

    result = call_radar_tool(container, "radar_audit_trail", {"entity_id": "test_123"})
    assert result.ok is True
    events = result.data
    assert len(events) == 1
    assert events[0]["actor"] == "test_user"
    assert events[0]["action"] == "test_action"
    assert events[0]["audit_id"] == audit_id
    assert events[0]["entity_type"] == "test_entity"
    assert events[0]["request_json"] is not None
    assert events[0]["result_json"] is not None
    assert events[0]["created_at"] is not None


def test_at_0_5_config_loads_and_validates(config_dir):
    """AT-0.5: Config Loads And Validates."""
    config = load_config(config_dir)
    assert config.scoring.version == "v1"
    assert "company_value" in config.scoring.weights
    assert "legacy_insolvency_scout" in config.sources
    assert config.sources["legacy_insolvency_scout"].mode == "read_only"
    assert all(source.enabled is False for source in config.sources.values())


def test_at_0_6_minimal_langgraph_workflow_runs(container):
    """AT-0.6: Minimal LangGraph Workflow Runs."""
    before_candidates = container.db.conn.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]
    before_source_runs = container.db.conn.execute(
        "SELECT COUNT(*) FROM source_runs"
    ).fetchone()[0]

    workflow = build_phase0_health_workflow(container)
    result = workflow.invoke({"actor": "test_user", "status": "running"})

    assert result["status"] == "success"
    assert result["database_connected"] is True
    assert result["schema_version"] == "002_audit_table"
    assert result["candidate_count"] == before_candidates
    assert result["source_run_count"] == before_source_runs
    assert result["audit_id"].startswith("audit_")

    after_candidates = container.db.conn.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]
    after_source_runs = container.db.conn.execute(
        "SELECT COUNT(*) FROM source_runs"
    ).fetchone()[0]
    assert after_candidates == before_candidates
    assert after_source_runs == before_source_runs

    audit_result = call_radar_tool(
        container,
        "radar_audit_trail",
        {"entity_type": "workflow", "entity_id": "phase0_health"},
    )
    assert audit_result.ok is True
    assert audit_result.data[0]["audit_id"] == result["audit_id"]


def test_at_0_7_safety_defaults(container, temp_db_path):
    """AT-0.7: Safety Defaults - legacy DB protection."""
    from biradar.services.import_legacy import LegacyImportInput

    # Attempting to use the active repo DB as legacy should fail
    params = LegacyImportInput(
        legacy_db_path=str(temp_db_path),
        dry_run=True,
    )
    result = container.legacy_import.import_legacy_scout(params, actor="test")

    assert result.ok is False
    assert any("INVALID_LEGACY_PATH" in err["code"] for err in result.errors)
