"""Output nodes: export-gated draft assembly, then Markdown/JSON export."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

import logging
from datetime import UTC, datetime
from typing import Any

from biradar.config.settings import get_settings
from biradar.graph.pipeline_workflow.node_helpers import _copied_warnings, _quarantine
from biradar.graph.state import PipelineWorkflowState
from biradar.output.export import generate_json_package, generate_markdown_draft

logger = logging.getLogger(__name__)


def draft_assembly_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Assemble export-ready Markdown and JSON."""
    logger.info("Executing draft assembly node")
    warnings = _copied_warnings(state)
    export_ready_candidates = []

    for candidate in state["candidates"]:
        if candidate.get("status") != "publish_ready":
            continue

        candidate_id = candidate.get("candidate_id", "unknown")
        score_payload = state.get("scores", {}).get(candidate_id)
        extraction_payload = state.get("extraction_results", {}).get(candidate_id, {})
        evidence_snippets = extraction_payload.get("evidence_snippets", {})
        if not score_payload or score_payload.get("status") != "approved":
            _exclude_from_export(
                candidate,
                warnings,
                candidate_id,
                "missing_approved_score",
                "missing approved score",
            )
            continue
        if not evidence_snippets:
            _exclude_from_export(
                candidate,
                warnings,
                candidate_id,
                "missing_evidence",
                "missing evidence",
            )
            continue

        enrichment_claims = (
            state.get("enrichment_results", {}).get(candidate_id, {}).get("claims", [])
        )
        factual_fields = _build_factual_fields(extraction_payload, candidate)
        _attach_export_metadata(
            candidate,
            score_payload,
            evidence_snippets,
            enrichment_claims,
            state,
            candidate_id,
        )
        candidate["content_sections"] = {
            "facts": factual_fields,
            "inferences": enrichment_claims,
            "editorial": {
                "score": score_payload,
                "thesis": (
                    "Ranked from deterministic score for "
                    f"{candidate.get('company_name', 'Unknown Company')}."
                ),
            },
        }
        export_ready_candidates.append(candidate)

    issue_draft = _build_issue_draft(state, export_ready_candidates, warnings)
    return {
        **state,
        "issue_draft": issue_draft,
        "warnings": warnings,
        "current_step": "export",
    }


def _exclude_from_export(
    candidate: dict[str, Any],
    warnings: list[str],
    candidate_id: str,
    reason: str,
    warning_text: str,
) -> None:
    """Quarantine a publish-ready candidate that fails an export gate."""
    _quarantine(candidate, reason)
    warnings.append(f"Excluded {candidate_id} from export: {warning_text}.")


def _build_factual_fields(
    extraction_payload: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Collect the extraction-backed factual fields, falling back to the record."""
    factual_fields: dict[str, Any] = {}
    for field in (
        "company_name",
        "case_number",
        "publication_date",
        "proceeding_stage",
    ):
        value = extraction_payload.get(field)
        if value is None:
            value = candidate.get(field)
        if value is not None:
            factual_fields[field] = value
    return factual_fields


def _attach_export_metadata(
    candidate: dict[str, Any],
    score_payload: dict[str, Any],
    evidence_snippets: dict[str, Any],
    enrichment_claims: list[dict[str, Any]],
    state: PipelineWorkflowState,
    candidate_id: str,
) -> None:
    """Attach the review confidence, evidence, and claim summaries for export."""
    candidate["export_confidence"] = (
        state.get("risk_reviews", {}).get(candidate_id, {}).get("confidence")
    )
    candidate["evidence_summary"] = evidence_snippets
    candidate["enrichment_claims"] = enrichment_claims
    candidate["unsupported_claims"] = (
        state.get("risk_reviews", {})
        .get(candidate_id, {})
        .get("unsupported_claims", [])
    )


def _build_issue_draft(
    state: PipelineWorkflowState,
    export_ready_candidates: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    """Assemble the issue draft with its audit summary."""
    total_candidates = len(state["candidates"])
    quarantined_candidates = len(
        [
            candidate
            for candidate in state["candidates"]
            if candidate.get("status") == "quarantined"
        ]
    )
    return {
        "title": "Weekly Berlin Insolvency Radar",
        "source_run_id": state.get("source_run_id"),
        "generated_at": datetime.now(UTC).isoformat(),
        "warnings": warnings,
        "audit_summary": {
            "source_run_id": state.get("source_run_id"),
            "total_raw_records": len(state.get("raw_records", [])),
            "total_candidates": total_candidates,
            "publish_ready_candidates": len(export_ready_candidates),
            "quarantined_candidates": quarantined_candidates,
            "error_count": len(state.get("errors", [])),
            "warning_count": len(warnings),
            "current_step": "draft_assembly",
        },
        "candidates": export_ready_candidates,
    }


def export_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Final export gate and persistence."""
    logger.info("Executing export node")
    settings = get_settings()
    export_dir = settings.data_dir / "exports"
    issue_data = state.get("issue_draft", {})
    markdown_path = generate_markdown_draft(issue_data, export_dir)
    json_path = generate_json_package(issue_data, export_dir)
    return {
        **state,
        "export_path": markdown_path,
        "warnings": state.get("warnings", [])
        + [f"Exported to {markdown_path} and {json_path}"],
        "current_step": "completed",
    }
