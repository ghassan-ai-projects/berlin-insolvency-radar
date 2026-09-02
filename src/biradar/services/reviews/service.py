"""Review service orchestration for candidate approval, rejection, and scoring."""

import logging
import uuid
from typing import Any

from biradar.config.settings import AppConfig
from biradar.domain.statuses import TRANSITION_RULES, validate_transition
from biradar.mcp.envelope import ResultEnvelope
from biradar.services.reviews.approval import _approve_candidate
from biradar.services.reviews.decisions import ALLOWED_DECISIONS, DECISION_TARGET_STATUS
from biradar.services.reviews.failures import _review_failure
from biradar.storage.db import Database
from biradar.storage.repository import (
    AuditRepository,
    CandidateRepository,
    ReviewRepository,
    ScoreRepository,
)

logger = logging.getLogger(__name__)


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
        if decision not in ALLOWED_DECISIONS:
            return _review_failure(
                self.audit_repo,
                reviewer=reviewer,
                candidate_id=candidate_id,
                decision=decision,
                score_input=score_input,
                error="invalid_decision",
                code="INVALID_DECISION",
                message=f"Decision must be one of {ALLOWED_DECISIONS}",
            )

        target_status = DECISION_TARGET_STATUS[decision]

        try:
            candidate = self.candidate_repo.get_by_id(candidate_id)
            if not candidate:
                return _review_failure(
                    self.audit_repo,
                    reviewer=reviewer,
                    candidate_id=candidate_id,
                    decision=decision,
                    score_input=score_input,
                    error="candidate_not_found",
                    code="CANDIDATE_NOT_FOUND",
                    message=f"No candidate found for {candidate_id}",
                )

            current_status = candidate["status"]
            is_valid, error_msg = validate_transition(current_status, target_status)
            if not is_valid:
                # Still audit the failed attempt
                return _review_failure(
                    self.audit_repo,
                    reviewer=reviewer,
                    candidate_id=candidate_id,
                    decision=decision,
                    score_input=score_input,
                    error=error_msg,
                    code="INVALID_TRANSITION",
                    message=error_msg,
                )

            transition_rule = TRANSITION_RULES.get(target_status)
            if (
                transition_rule
                and transition_rule.requires_note
                and not (note and note.strip())
            ):
                return _review_failure(
                    self.audit_repo,
                    reviewer=reviewer,
                    candidate_id=candidate_id,
                    decision=decision,
                    score_input=score_input,
                    error="note_required",
                    code="NOTE_REQUIRED",
                    message=f"Decision '{decision}' requires a note.",
                )

            computed_score = None
            computed_category = None
            score_id = None

            if decision == "approve":
                approval = _approve_candidate(
                    self.audit_repo,
                    self.score_repo,
                    self.config,
                    candidate_id,
                    reviewer,
                    score_input,
                )
                if isinstance(approval, ResultEnvelope):
                    return approval
                score_id, computed_score, computed_category = approval

            self.candidate_repo.update_status(candidate_id, target_status)

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

            audit_id = self.audit_repo.log_event(
                actor=reviewer,
                action="candidate_reviewed",
                entity_type="candidate",
                entity_id=candidate_id,
                request_data={"decision": decision, "score_input": score_input},
                result_data={"new_status": target_status, "score_id": score_id},
            )

            return ResultEnvelope(
                ok=True,
                data={
                    "candidate_id": candidate_id,
                    "status": target_status,
                    "decision": decision,
                    "score_id": score_id,
                    "computed_score": computed_score,
                    "computed_category": computed_category,
                },
                audit_id=audit_id,
                next_action="Call radar_list_candidates to see remaining items, or radar_create_issue_draft if ready.",
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
