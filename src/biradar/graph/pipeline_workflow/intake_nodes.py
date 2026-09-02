"""Intake nodes: seeding, normalization, compliance gating, and dedupe."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

import logging
from typing import Any

from biradar.domain.compliance import evaluate_compliance
from biradar.domain.dedupe import deduplicate_candidates
from biradar.graph.state import PipelineWorkflowState

logger = logging.getLogger(__name__)


def ingest_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Initial node: seed the state from already-fetched raw records."""
    logger.info("Executing ingest node")
    return {**state, "current_step": "normalize"}


def normalize_and_compliance_node(
    state: PipelineWorkflowState,
) -> PipelineWorkflowState:
    """Normalize records and apply deterministic corporate-only filtering.

    Records whose raw_record_id already has a linked candidate in the DB
    are skipped — avoids re-processing on pipeline re-runs.
    """
    logger.info("Executing normalize and compliance node")
    already_processed = set(state.get("already_processed_raw_ids", []))
    valid_candidates = [
        _normalize_record(record, already_processed) for record in state["raw_records"]
    ]
    return {**state, "candidates": valid_candidates, "current_step": "dedupe"}


def _normalize_record(
    record: dict[str, Any], already_processed: set[str]
) -> dict[str, Any]:
    """Quarantine records processed on earlier runs; gate the rest on compliance."""
    raw_id = record.get("raw_record_id")
    if raw_id and raw_id in already_processed:
        return {
            **record,
            "status": "quarantined",
            "quarantine_reason": "already_processed",
        }

    is_allowed, reason = evaluate_compliance(
        legal_form=record.get("legal_form"),
        raw_text=record.get("raw_text", ""),
        company_name=record.get("company_name"),
    )
    status = "deduped_candidate" if is_allowed else "quarantined"
    return {
        **record,
        "status": status,
        "compliance_reason": None if is_allowed else reason,
    }


def dedupe_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Deterministic deduplication."""
    logger.info("Executing dedupe node")
    deduped = deduplicate_candidates(state["candidates"])
    return {**state, "candidates": deduped, "current_step": "extraction"}
