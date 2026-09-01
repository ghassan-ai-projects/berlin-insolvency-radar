"""Risk review node: LLM review with evidence policy and limited retry."""

# pyright: reportArgumentType=false, reportReturnType=false
#
# Scoped to this module. Two upstream limitations, neither first-party:
#   * `{**state, ...}` over a TypedDict widens to a plain dict, so every node
#     return is reported as not assignable to PipelineWorkflowState.
#   * StateGraph.add_node passes an unbound NodeInputT that does not resolve to
#     the concrete state type.
# Keep these off only here; the rules stay enabled everywhere else.

import logging
from collections.abc import Mapping
from typing import Any, Literal

from biradar.agents.risk_review import review_candidate_risk
from biradar.graph.pipeline_workflow.node_helpers import (
    _active_candidates,
    _copied_errors,
    _copied_warnings,
    _quarantine,
)
from biradar.graph.pipeline_workflow.types import RiskReviewerFn
from biradar.graph.state import PipelineWorkflowState, RiskReviewPayload

logger = logging.getLogger(__name__)

_MAX_REVIEW_RETRIES = 2


def risk_review_node(
    state: PipelineWorkflowState,
    risk_reviewer: RiskReviewerFn = review_candidate_risk,
) -> PipelineWorkflowState:
    """Risk review with limited retry before quarantine."""
    logger.info("Executing risk review node")

    retry_counts = dict(state.get("retry_counts", {}))
    risk_reviews: dict[str, RiskReviewPayload] = dict(state.get("risk_reviews", {}))
    warnings = _copied_warnings(state)
    errors = _copied_errors(state)
    needs_retry = False

    for candidate in _active_candidates(state.get("candidates", [])):
        candidate_id = candidate.get("candidate_id", "unknown")
        retries = retry_counts.get(candidate_id, 0)
        extraction_data = state.get("extraction_results", {}).get(candidate_id, {})
        enrichment_data = state.get("enrichment_results", {}).get(candidate_id, {})
        evidence_snippets = extraction_data.get("evidence_snippets", {})

        # Build a fact-rich thesis from available extraction evidence
        draft_thesis = _build_review_thesis(
            candidate, extraction_data, evidence_snippets
        )

        unsupported_claims = _unsupported_claims_in(enrichment_data)
        if unsupported_claims:
            _quarantine_unsupported_claims(
                candidate,
                risk_reviews,
                warnings,
                candidate_id,
                retries,
                unsupported_claims,
            )
            continue

        if not evidence_snippets:
            _quarantine_missing_evidence(
                candidate, risk_reviews, warnings, candidate_id, retries
            )
            continue

        try:
            if _review_and_settle(
                candidate,
                risk_reviews,
                retry_counts,
                risk_reviewer,
                candidate_id,
                retries,
                extraction_data,
                enrichment_data,
                draft_thesis,
            ):
                needs_retry = True
        except Exception as exc:
            logger.error("Risk review failed for %s: %s", candidate_id, exc)
            errors.append(f"Risk review failed for {candidate_id}: {exc}")
            _quarantine(candidate, "risk_review_system_error")

    current_step: Literal["extraction", "draft_assembly"]
    current_step = "extraction" if needs_retry else "draft_assembly"
    return {
        **state,
        "retry_counts": retry_counts,
        "risk_reviews": risk_reviews,
        "warnings": warnings,
        "errors": errors,
        "current_step": current_step,
    }


def _build_review_thesis(
    candidate: Mapping[str, Any],
    extraction_data: Mapping[str, Any],
    evidence_snippets: Mapping[str, Any],
) -> str:
    """Compose the fact-rich thesis line handed to the risk reviewer."""
    facts = []
    company = extraction_data.get("company_name") or candidate.get(
        "company_name", "Unknown"
    )
    legal = extraction_data.get("legal_form") or candidate.get("legal_form", "")
    case_no = extraction_data.get("case_number") or candidate.get("case_number", "")
    court = extraction_data.get("court") or candidate.get("court", "")
    filing = extraction_data.get("filing_date") or candidate.get("publication_date", "")
    stage = extraction_data.get("proceeding_stage") or candidate.get(
        "proceeding_stage", ""
    )

    if company:
        facts.append(company)
    if legal:
        facts.append(f"a {legal}")
    if case_no:
        facts.append(f"case {case_no}")
    if court:
        facts.append(f"at {court}")
    if filing:
        facts.append(f"filed {filing}")
    if stage:
        facts.append(f"stage: {stage}")

    fact_line = (
        ", ".join(facts) if facts else f"for {candidate.get('company_name', 'Unknown')}"
    )
    return (
        f"Potential opportunity involving {fact_line}. "
        f"Evidence includes {len(evidence_snippets)} verified fields from the official insolvency register."
    )


def _unsupported_claims_in(enrichment_data: Mapping[str, Any]) -> list[Any]:
    """List enrichment claims that are neither inference-classified nor sourced."""
    return [
        claim
        for claim in enrichment_data.get("claims", [])
        if claim.get("classification") != "inference" and not claim.get("source_url")
    ]


def _quarantine_unsupported_claims(
    candidate: dict[str, Any],
    risk_reviews: dict[str, RiskReviewPayload],
    warnings: list[str],
    candidate_id: str,
    retries: int,
    unsupported_claims: list[Any],
) -> None:
    """Quarantine a candidate whose enrichment claims lack sourcing."""
    _quarantine(candidate, "unsupported_enrichment_claims")
    risk_reviews[candidate_id] = {
        "status": "quarantined",
        "retries": retries,
        "reasons": ["unsupported_enrichment_claims"],
        "unsupported_claims": unsupported_claims,
    }
    warnings.append(f"Quarantined {candidate_id}: unsupported enrichment claims.")


def _quarantine_missing_evidence(
    candidate: dict[str, Any],
    risk_reviews: dict[str, RiskReviewPayload],
    warnings: list[str],
    candidate_id: str,
    retries: int,
) -> None:
    """Quarantine a candidate whose extraction produced no evidence."""
    _quarantine(candidate, "missing_extraction_evidence")
    risk_reviews[candidate_id] = {
        "status": "quarantined",
        "retries": retries,
        "reasons": ["missing_extraction_evidence"],
        "unsupported_claims": [],
    }
    warnings.append(f"Quarantined {candidate_id}: missing extraction evidence.")


def _review_and_settle(
    candidate: dict[str, Any],
    risk_reviews: dict[str, RiskReviewPayload],
    retry_counts: dict[str, int],
    risk_reviewer: RiskReviewerFn,
    candidate_id: str,
    retries: int,
    extraction_data: Mapping[str, Any],
    enrichment_data: Mapping[str, Any],
    draft_thesis: str,
) -> bool:
    """Run one review attempt and settle its outcome on the candidate.

    Returns True when the review failed and another retry pass is needed.
    Raises through when the reviewer itself errors; the caller records that.
    """
    result = risk_reviewer(candidate, extraction_data, enrichment_data, draft_thesis)
    if not result.passed_review:
        if retries < _MAX_REVIEW_RETRIES:
            retry_counts[candidate_id] = retries + 1
            return True
        _quarantine(candidate, "risk_review_failed_max_retries")
        risk_reviews[candidate_id] = {
            "status": "quarantined",
            "retries": retries,
            "reasons": result.rejection_reasons or ["review_rejected"],
        }
        return False

    candidate["status"] = "publish_ready"
    risk_reviews[candidate_id] = {
        "status": "passed",
        "retries": retries,
        "confidence": result.confidence_in_review,
        "unsupported_claims": [],
    }
    return False
