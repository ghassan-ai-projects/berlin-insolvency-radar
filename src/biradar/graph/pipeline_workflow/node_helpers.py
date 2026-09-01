"""Shared candidate-level helpers used by the pipeline nodes."""

from typing import Any

from biradar.graph.state import PipelineWorkflowState


def _quarantine(candidate: dict[str, Any], reason: str) -> None:
    """Flag a candidate in place as quarantined with the given reason."""
    candidate["status"] = "quarantined"
    candidate["quarantine_reason"] = reason


def _active_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter out candidates already quarantined by an earlier stage.

    The candidate dicts themselves are returned uncopied: stages mutate them
    in place on purpose (LangGraph checkpoint re-entry relies on the aliasing).
    """
    return [
        candidate
        for candidate in candidates
        if candidate.get("status") != "quarantined"
    ]


def _copied_errors(state: PipelineWorkflowState) -> list[str]:
    """Start a fresh error accumulator from the state's existing errors."""
    return list(state.get("errors", []))


def _copied_warnings(state: PipelineWorkflowState) -> list[str]:
    """Start a fresh warning accumulator from the state's existing warnings."""
    return list(state.get("warnings", []))
