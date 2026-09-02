"""Scoring node: deterministic scores from extraction evidence only."""

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
from typing import Any

from biradar.config.settings import get_settings, load_config
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.graph.pipeline_workflow.node_helpers import (
    _active_candidates,
    _quarantine,
)
from biradar.graph.state import PipelineWorkflowState, ScorePayload

logger = logging.getLogger(__name__)


def scoring_node(state: PipelineWorkflowState) -> PipelineWorkflowState:
    """Deterministic scoring from extraction evidence only.

    Enrichment hasn't run yet — scores are based on what the LLM extracted.
    """
    logger.info("Executing scoring node")
    settings = get_settings()
    config = load_config(settings.project_root / "config")
    scores: dict[str, ScorePayload] = dict(state.get("scores", {}))

    for candidate in _active_candidates(state["candidates"]):
        candidate_id = candidate.get("candidate_id", "unknown")
        if candidate_id in scores and scores[candidate_id].get("status") == "approved":
            continue  # already scored on previous pass
        extraction_data = state.get("extraction_results", {}).get(candidate_id, {})

        try:
            score_payload, computed_score = _score_candidate(
                candidate, extraction_data, config
            )
            scores[candidate_id] = score_payload
            candidate["score"] = score_payload

            threshold = config.scoring.thresholds.get("interesting", 2.0)
            if computed_score < threshold:
                _quarantine(candidate, "low_score")
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", candidate_id, exc)
            scores[candidate_id] = {"status": "failed", "error": str(exc)}
            _quarantine(candidate, "scoring_failed")

    return {**state, "scores": scores, "current_step": "enrichment"}


def _score_candidate(
    candidate: Mapping[str, Any],
    extraction_data: Mapping[str, Any],
    config: Any,
) -> tuple[ScorePayload, float]:
    """Compute one candidate's score payload and its numeric score."""
    proposed_scores = _build_score_input(candidate, extraction_data)
    result = compute_score(
        proposed_scores, config.scoring.weights, config.scoring.thresholds
    )
    score_payload: ScorePayload = {
        "company_value": proposed_scores.company_value,
        "asset_quality": proposed_scores.asset_quality,
        "sector_attractiveness": proposed_scores.sector_attractiveness,
        "speed_of_action": proposed_scores.speed_of_action,
        "legal_risk": proposed_scores.legal_risk,
        "computed_score": result.computed_score,
        "category": result.category,
        "status": "approved",
        "rationale": proposed_scores.rationale,
    }
    return score_payload, result.computed_score


def _clamp_score(value: int) -> int:
    """Keep a heuristic dimension inside the 1..5 scoring range."""
    return max(1, min(5, value))


def _build_score_input(
    candidate: Mapping[str, Any],
    extraction_data: Mapping[str, Any],
) -> ScoreInput:
    """Build deterministic score dimensions from extraction evidence only.

    Enrichment data is collected later for export-quality candidates only.
    """
    legal_form = (
        candidate.get("legal_form") or extraction_data.get("legal_form") or ""
    ).upper()
    stage = (
        candidate.get("proceeding_stage")
        or extraction_data.get("proceeding_stage")
        or ""
    ).lower()
    evidence_count = len(extraction_data.get("evidence_snippets", {}))

    company_value = 2
    if legal_form in {"GMBH", "AG", "SE", "GMBH & CO. KG"}:
        company_value += 1

    asset_quality = 2
    sector_attractiveness = 2
    speed_of_action = 3 + int("er" in stage) + int(evidence_count >= 2)
    legal_risk = 3 - int(evidence_count >= 2)

    return ScoreInput(
        company_value=_clamp_score(company_value),
        asset_quality=_clamp_score(asset_quality),
        sector_attractiveness=_clamp_score(sector_attractiveness),
        speed_of_action=_clamp_score(speed_of_action),
        legal_risk=_clamp_score(legal_risk),
        rationale={
            "method": "deterministic_heuristics_extraction_only",
            "evidence_count": str(evidence_count),
        },
    )
