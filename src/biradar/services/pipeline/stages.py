"""Stage-report bookkeeping and result-dict builders for the pipeline runner."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Any


def _pending_stage_report() -> dict[str, dict[str, Any]]:
    """Create the stage report skeleton with every stage pending."""
    return {
        "fetch": {"status": "pending"},
        "workflow": {"status": "pending"},
        "persist": {"status": "pending"},
    }


def _start_stage(stage_report: dict[str, dict[str, Any]], name: str) -> float:
    stage_report[name] = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
    }
    return perf_counter()


def _finish_stage(
    stage_report: dict[str, dict[str, Any]],
    name: str,
    started_at: float,
    status: str,
    **details: Any,
) -> None:
    stage_report[name] = {
        **stage_report.get(name, {}),
        "status": status,
        "completed_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(perf_counter() - started_at, 3),
        **details,
    }


def _fail_result(
    stage_report: dict[str, dict[str, Any]],
    stage_name: str,
    started_at: float,
    error: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    _finish_stage(
        stage_report,
        stage_name,
        started_at,
        "failed",
        error=error,
    )
    return {
        "status": "failed",
        "error": error,
        "errors": errors or [error],
        "stage_report": stage_report,
    }


def _portal_only_result(stage_report: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the short-circuit result for a fetch-only run."""
    return {
        "status": "success",
        "current_step": "fetched",
        "export_path": None,
        "issue_id": None,
        "warnings": [],
        "errors": [],
        "stage_report": stage_report,
    }


def _success_result(
    final_state: dict[str, Any],
    issue_id: str | None,
    stage_report: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "success",
        "current_step": final_state.get("current_step"),
        "export_path": final_state.get("export_path"),
        "issue_id": issue_id,
        "warnings": final_state.get("warnings", []),
        "errors": final_state.get("errors", []),
        "stage_report": stage_report,
    }
