"""Score validation and approved-score persistence for candidate approval."""

import json
import uuid
from typing import Any

from biradar.config.settings import AppConfig
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.mcp.envelope import ResultEnvelope
from biradar.services.reviews.failures import _review_failure
from biradar.storage.repository import AuditRepository, ScoreRepository


def _approve_candidate(
    audit_repo: AuditRepository,
    score_repo: ScoreRepository,
    config: AppConfig,
    candidate_id: str,
    reviewer: str,
    score_input: dict[str, Any] | None,
) -> tuple[str, Any, Any] | ResultEnvelope[dict[str, Any]]:
    """Validate, compute, and store the approval score.

    Returns (score_id, computed_score, computed_category), or a failure
    envelope when the dimensions are missing or invalid.
    """
    if not score_input:
        return _review_failure(
            audit_repo,
            reviewer=reviewer,
            candidate_id=candidate_id,
            decision="approve",
            score_input=score_input,
            error="missing_score",
            code="MISSING_SCORE",
            message="Approving a candidate requires score dimensions.",
        )

    try:
        validated_input = ScoreInput(**score_input)
    except Exception as e:
        return _review_failure(
            audit_repo,
            reviewer=reviewer,
            candidate_id=candidate_id,
            decision="approve",
            score_input=score_input,
            error=str(e),
            code="INVALID_SCORE_INPUT",
            message=str(e),
        )

    score_result = compute_score(
        validated_input,
        config.scoring.weights,
        config.scoring.thresholds,
    )
    score_id = f"score_{uuid.uuid4().hex}"

    score_repo.insert_score(
        score_id=score_id,
        candidate_id=candidate_id,
        score_version=config.scoring.version,
        company_value=validated_input.company_value,
        asset_quality=validated_input.asset_quality,
        sector_attractiveness=validated_input.sector_attractiveness,
        speed_of_action=validated_input.speed_of_action,
        legal_risk=validated_input.legal_risk,
        computed_score=score_result.computed_score,
        category=score_result.category,
        rationale_json=json.dumps(validated_input.rationale),
        status="approved",
        reviewer=reviewer,
    )
    return score_id, score_result.computed_score, score_result.category
