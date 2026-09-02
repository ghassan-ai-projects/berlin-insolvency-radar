"""Error envelope builders for the radar tool dispatch."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope


def validation_error(message: str) -> ResultEnvelope[Any]:
    """Build a stable validation failure envelope."""
    return ResultEnvelope(
        ok=False,
        errors=[
            {
                "code": "VALIDATION_ERROR",
                "message": message,
                "retryable": False,
                "next_action": "Fix the tool arguments and retry.",
            }
        ],
        next_action="Fix the tool arguments and retry.",
    )


def tool_not_found_error(name: str) -> ResultEnvelope[Any]:
    """Build the unknown-tool failure envelope."""
    return ResultEnvelope(
        ok=False,
        errors=[
            {
                "code": "TOOL_NOT_FOUND",
                "message": f"Unknown tool: {name}",
                "retryable": False,
            }
        ],
    )


def internal_error() -> ResultEnvelope[Any]:
    """Build the generic failure envelope (details stay in the log)."""
    return ResultEnvelope(
        ok=False,
        errors=[
            {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred.",
                "retryable": True,
            }
        ],
    )
