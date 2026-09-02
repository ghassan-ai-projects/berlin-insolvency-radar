"""Radar tool dispatch shared by the MCP server and the test suite."""

import logging
from typing import Any

from mcp.types import Tool
from pydantic import ValidationError

from biradar.mcp.envelope import ResultEnvelope
from biradar.mcp.server.errors import (
    internal_error,
    tool_not_found_error,
    validation_error,
)
from biradar.mcp.server.specs import _tool_specs
from biradar.services.container import AppContainer

# The dispatch moved into a submodule, but log records keep the original
# "biradar.mcp.server" logger name.
logger = logging.getLogger("biradar.mcp.server")


def list_radar_tools() -> list[Tool]:
    """Return the MCP tool definitions derived from schema models."""
    return [
        Tool(
            name=spec.name,
            description=spec.description,
            inputSchema=spec.input_model.model_json_schema(),
        )
        for spec in _tool_specs()
    ]


def call_radar_tool(
    container: AppContainer, name: str, arguments: dict[str, Any] | None = None
) -> ResultEnvelope[Any]:
    """Execute a radar tool through the same path used by MCP."""
    args = arguments or {}
    spec_by_name = {spec.name: spec for spec in _tool_specs()}

    try:
        spec = spec_by_name.get(name)
        if spec is None:
            return tool_not_found_error(name)

        params = spec.input_model(**args)
        return spec.handler(container, params)
    except ValidationError as e:
        return validation_error(str(e))
    except Exception:
        logger.exception("Unhandled error in radar tool dispatch", extra={"tool": name})
        return internal_error()
