"""Review service for candidate approval, rejection, and scoring."""

import json
import uuid
from typing import Any

from biradar.config.settings import AppConfig
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.domain.statuses import TRANSITION_RULES, validate_transition
from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    ReviewRepository,
    ScoreRepository,
)


class ReviewService:
    def __init__(self, db: Database, config: AppConfig):
        self.db = db
        self.config = config
        self.candidate_repo = CandidateRepository(db)
        self.review_repo = ReviewRepository(db)
        self.score_repo = ScoreRepository(db)
        self.audit_repo = AuditRepository(db)

    def review_candidate(
        self,
        candidate_id: str,
        decision: str,
        reviewer: str,
        note: str | None = None,
        score_input: dict[str, Any] | None = None,
    ) -> ResultEnvelope[dict[str, Any]]:
        """
        Review a candidate: approve, reject, needs_more_info, mark_duplicate, or archive.
        """
        allowed_decisions = {
            "approve",
            "reject",
            "needs_more_info",
            "mark_duplicate",
            "archive",
        }
        if decision not in allowed_decisions:
            audit_id = self.audit_repo.log_event(
                actor=reviewer,
                action="candidate_review_failed",
                entity_type="candidate",
                entity_id=candidate_id,
                request_data={"decision": decision, "score_input": score_input},
                result_data={"error": "invalid_decision"},
            )
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "INVALID_DECISION",
                        "message": f"Decision must be one of {allowed_decisions}",
                        "retryable": False,
                    }
                ],
                audit_id=audit_id,
            )

        status_map = {
            "approve": "publish_ready",
            "reject": "rejected",
            "needs_more_info": "needs_review",
            "mark_duplicate": "duplicate",
            "archive": "archived",
        }
        target_status = status_map[decision]

        try:
            candidate = self.candidate_repo.get_by_id(candidate_id)
            if not candidate:
                audit_id = self.audit_repo.log_event(
                    actor=reviewer,
                    action="candidate_review_failed",
                    entity_type="candidate",
                    entity_id=candidate_id,
                    request_data={"decision": decision, "score_input": score_input},
                    result_data={"error": "candidate_not_found"},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "CANDIDATE_NOT_FOUND",
                            "message": f"No candidate found for {candidate_id}",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            current_status = candidate["status"]
            is_valid, error_msg = validate_transition(current_status, target_status)
            if not is_valid:
                # Still audit the failed attempt
                audit_id = self.audit_repo.log_event(
                    actor=reviewer,
                    action="candidate_review_failed",
                    entity_type="candidate",
                    entity_id=candidate_id,
                    request_data={"decision": decision, "score_input": score_input},
                    result_data={"error": error_msg},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_TRANSITION",
                            "message": error_msg,
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            transition_rule = TRANSITION_RULES.get(target_status)
            if (
                transition_rule
                and transition_rule.requires_note
                and not (note and note.strip())
            ):
                audit_id = self.audit_repo.log_event(
                    actor=reviewer,
                    action="candidate_review_failed",
                    entity_type="candidate",
                    entity_id=candidate_id,
                    request_data={"decision": decision, "score_input": score_input},
                    result_data={"error": "note_required"},
                )
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "NOTE_REQUIRED",
                            "message": f"Decision '{decision}' requires a note.",
                            "retryable": False,
                        }
                    ],
                    audit_id=audit_id,
                )

            computed_score = None
            computed_category = None
            score_id = None

            # If approving, validate and compute score
            if decision == "approve":
                if not score_input:
                    audit_id = self.audit_repo.log_event(
                        actor=reviewer,
                        action="candidate_review_failed",
                        entity_type="candidate",
                        entity_id=candidate_id,
                        request_data={"decision": decision, "score_input": score_input},
                        result_data={"error": "missing_score"},
                    )
                    return ResultEnvelope(
                        ok=False,
                        errors=[
                            {
                                "code": "MISSING_SCORE",
                                "message": "Approving a candidate requires score dimensions.",
                                "retryable": False,
                            }
                        ],
                        audit_id=audit_id,
                    )

                try:
                    validated_input = ScoreInput(**score_input)
                except Exception as e:
                    audit_id = self.audit_repo.log_event(
                        actor=reviewer,
                        action="candidate_review_failed",
                        entity_type="candidate",
                        entity_id=candidate_id,
                        request_data={"decision": decision, "score_input": score_input},
                        result_data={"error": str(e)},
                    )
                    return ResultEnvelope(
                        ok=False,
                        errors=[
                            {
                                "code": "INVALID_SCORE_INPUT",
                                "message": str(e),
                                "retryable": False,
                            }
                        ],
                        audit_id=audit_id,
                    )

                result = compute_score(
                    validated_input,
                    self.config.scoring.weights,
                    self.config.scoring.thresholds,
                )
                computed_score = result.computed_score
                computed_category = result.category
                score_id = f"score_{uuid.uuid4().hex}"

                self.score_repo.insert_score(
                    score_id=score_id,
                    candidate_id=candidate_id,
                    score_version=self.config.scoring.version,
                    company_value=validated_input.company_value,
                    asset_quality=validated_input.asset_quality,
                    sector_attractiveness=validated_input.sector_attractiveness,
                    speed_of_action=validated_input.speed_of_action,
                    legal_risk=validated_input.legal_risk,
                    computed_score=computed_score,
                    category=computed_category,
                    rationale_json=json.dumps(validated_input.rationale),
                    status="approved",
                    reviewer=reviewer,
                )
            # Update candidate status
            self.candidate_repo.update_status(candidate_id, target_status)

            # Insert review record
            review_id = f"rev_{uuid.uuid4().hex}"
            self.review_repo.insert_review(
                review_id=review_id,
                candidate_id=candidate_id,
                reviewer=reviewer,
                decision=decision,
                from_status=current_status,
                to_status=target_status,
                note=note,
            )

            # Write audit event
            audit_id = self.audit_repo.log_event(
                actor=reviewer,
                action="candidate_reviewed",
                entity_type="candidate",
                entity_id=candidate_id,
                request_data={"decision": decision, "score_input": score_input},
                result_data={"new_status": target_status, "score_id": score_id},
            )

            response_data = {
                "candidate_id": candidate_id,
                "status": target_status,
                "decision": decision,
                "score_id": score_id,
                "computed_score": computed_score,
                "computed_category": computed_category,
            }

            next_action = "Call radar_list_candidates to see remaining items, or radar_create_issue_draft if ready."

            return ResultEnvelope(
                ok=True,
                data=response_data,
                audit_id=audit_id,
                next_action=next_action,
            )

        except Exception as e:
            error_msg = str(e)
            self.audit_repo.log_event(
                actor=reviewer,
                action="candidate_review_exception",
                entity_type="candidate",
                entity_id=candidate_id,
                request_data={"decision": decision},
                result_data={"error": error_msg},
            )
            return ResultEnvelope(
                ok=False,
                errors=[
                    {"code": "REVIEW_FAILED", "message": error_msg, "retryable": True}
                ],
            )
