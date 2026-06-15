"""Review service for candidate approval, rejection, and scoring."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from biradar.config.settings import AppConfig
from biradar.domain.scoring import ScoreInput, compute_score
from biradar.domain.statuses import validate_transition
from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import AuditRepository, CandidateRepository


class ReviewService:
    def __init__(self, db: Database, config: AppConfig):
        self.db = db
        self.config = config
        self.candidate_repo = CandidateRepository(db)
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
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "INVALID_DECISION",
                        "message": f"Decision must be one of {allowed_decisions}",
                        "retryable": False,
                    }
                ],
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
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "CANDIDATE_NOT_FOUND",
                            "message": f"No candidate found for {candidate_id}",
                            "retryable": False,
                        }
                    ],
                )

            current_status = candidate["status"]
            is_valid, error_msg = validate_transition(current_status, target_status)
            if not is_valid:
                return ResultEnvelope(
                    ok=False,
                    errors=[
                        {
                            "code": "INVALID_TRANSITION",
                            "message": error_msg,
                            "retryable": False,
                        }
                    ],
                )

            audit_data: dict[str, Any] = {
                "candidate_id": candidate_id,
                "decision": decision,
                "from_status": current_status,
                "to_status": target_status,
                "reviewer": reviewer,
                "note": note,
            }

            computed_score = None
            computed_category = None
            score_id = None

            # If approving, validate and compute score
            if decision == "approve":
                if not score_input:
                    return ResultEnvelope(
                        ok=False,
                        errors=[
                            {
                                "code": "MISSING_SCORE",
                                "message": "Approving a candidate requires score dimensions.",
                                "retryable": False,
                            }
                        ],
                    )

                try:
                    validated_input = ScoreInput(**score_input)
                except Exception as e:
                    return ResultEnvelope(
                        ok=False,
                        errors=[
                            {
                                "code": "INVALID_SCORE_INPUT",
                                "message": str(e),
                                "retryable": False,
                            }
                        ],
                    )

                result = compute_score(
                    validated_input,
                    self.config.scoring.weights,
                    self.config.scoring.thresholds,
                )
                computed_score = result.computed_score
                computed_category = result.category
                score_id = f"score_{uuid.uuid4().hex}"

                # Insert score
                now_str = datetime.now(UTC).isoformat()
                self.db.conn.execute(
                    """
                    INSERT INTO scores 
                    (score_id, candidate_id, score_version, company_value, asset_quality, 
                     sector_attractiveness, speed_of_action, legal_risk, computed_score, category, 
                     rationale_json, status, reviewer, created_at, approved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)
                    """,
                    [
                        score_id,
                        candidate_id,
                        self.config.scoring.version,
                        validated_input.company_value,
                        validated_input.asset_quality,
                        validated_input.sector_attractiveness,
                        validated_input.speed_of_action,
                        validated_input.legal_risk,
                        computed_score,
                        computed_category,
                        json.dumps(validated_input.rationale),
                        reviewer,
                        now_str,
                        now_str,
                    ],
                )
                audit_data["score_id"] = score_id
                audit_data["computed_score"] = computed_score

            # Update candidate status
            self.candidate_repo.update_status(candidate_id, target_status)

            # Insert review record
            review_id = f"rev_{uuid.uuid4().hex}"
            now_str = datetime.now(UTC).isoformat()
            self.db.conn.execute(
                """
                INSERT INTO reviews 
                (review_id, candidate_id, reviewer, decision, from_status, to_status, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    review_id,
                    candidate_id,
                    reviewer,
                    decision,
                    current_status,
                    target_status,
                    note,
                    now_str,
                ],
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
            return ResultEnvelope(
                ok=False,
                errors=[
                    {"code": "REVIEW_FAILED", "message": str(e), "retryable": True}
                ],
            )
