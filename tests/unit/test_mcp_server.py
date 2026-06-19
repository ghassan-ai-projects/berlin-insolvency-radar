"""Unit tests for MCP tool contract registration and dispatch."""

import tempfile
from pathlib import Path

from biradar.mcp.server import call_radar_tool, list_radar_tools
from biradar.services.container import AppContainer


def test_list_radar_tools_uses_pydantic_schema_contracts():
    tools = {tool.name: tool for tool in list_radar_tools()}

    assert "radar_run_workflow" in tools
    assert set(tools["radar_run_workflow"].inputSchema["required"]) == {
        "start_date",
        "end_date",
    }
    assert (
        "legacy_db_path" in tools["radar_import_legacy_scout"].inputSchema["properties"]
    )


def test_call_radar_tool_returns_stable_unknown_tool_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        container = AppContainer(
            Path(__file__).parent.parent.parent / "config",
            Path(tmpdir) / "mcp_server.duckdb",
        )
        try:
            result = call_radar_tool(container, "radar_not_real", {})
        finally:
            container.close()

    assert result.ok is False
    assert result.errors[0]["code"] == "TOOL_NOT_FOUND"


def test_call_radar_tool_validates_against_registered_schema():
    with tempfile.TemporaryDirectory() as tmpdir:
        container = AppContainer(
            Path(__file__).parent.parent.parent / "config",
            Path(tmpdir) / "mcp_server_validation.duckdb",
        )
        try:
            result = call_radar_tool(container, "radar_run_workflow", {"dry_run": True})
        finally:
            container.close()

    assert result.ok is False
    assert result.errors[0]["code"] == "VALIDATION_ERROR"
