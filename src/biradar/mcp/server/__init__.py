"""MCP Server for Berlin Insolvency Radar.

The public surface is re-exported so consumers keep importing from
``biradar.mcp.server``. Nothing patches this package at module level; the
CLI's monkeypatch strings resolve against ``biradar.cli.main`` attributes.
"""

from biradar.mcp.server.api import (
    call_radar_tool,
    list_radar_tools,
    validation_error,
)
from biradar.mcp.server.runtime import create_mcp_server
from biradar.mcp.server.specs import RadarToolSpec

__all__ = [
    "RadarToolSpec",
    "call_radar_tool",
    "create_mcp_server",
    "list_radar_tools",
    "validation_error",
]
