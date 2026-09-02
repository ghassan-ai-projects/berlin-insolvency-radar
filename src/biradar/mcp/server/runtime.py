"""MCP protocol server assembly (stdio serving lives in the CLI)."""

import json
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool

from biradar.mcp.envelope import ResultEnvelope
from biradar.mcp.server.api import call_radar_tool, list_radar_tools
from biradar.services.container import AppContainer


def create_mcp_server(config_dir: Path, db_path: Path) -> Server:
    """Create and configure the MCP server."""
    server = Server("biradar")
    container = AppContainer(config_dir, db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return list_radar_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = call_radar_tool(container, name, arguments)
        return [_envelope_to_text(result)]

    return server


def _envelope_to_text(result: ResultEnvelope) -> TextContent:
    """Serialize an envelope for the wire; default=str carries dates/Paths."""
    return TextContent(
        type="text",
        text=json.dumps(result.model_dump(), indent=2, default=str),
    )
