"""Path validation guards for the legacy import."""

from pathlib import Path
from typing import Any

from biradar.mcp.envelope import ResultEnvelope


def _guard_rejection(code: str, message: str) -> ResultEnvelope[dict[str, Any]]:
    return ResultEnvelope(
        ok=False,
        errors=[{"code": code, "message": message, "retryable": False}],
    )


def _validate_legacy_path(
    legacy_path: Path, repo_db_path: str
) -> ResultEnvelope[dict[str, Any]] | None:
    """Reject the repo database itself and missing legacy files."""
    if str(legacy_path.absolute()) == repo_db_path:
        return _guard_rejection(
            "INVALID_LEGACY_PATH",
            "Legacy path cannot be the active repo database.",
        )
    if not legacy_path.exists():
        return _guard_rejection(
            "FILE_NOT_FOUND", f"Legacy database not found at {legacy_path}"
        )
    return None
