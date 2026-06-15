"""Candidate service for querying and listing candidates."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import (
    CandidateRepository,
    EvidenceRepository,
    RawRecordRepository,
    ReviewRepository,
    ScoreRepository,
)


class CandidateService:
    def __init__(self, db: Database):
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.review_repo = ReviewRepository(db)
        self.score_repo = ScoreRepository(db)
        self.raw_repo = RawRecordRepository(db)

    def list_candidates(
        self,
        statuses: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> ResultEnvelope[list[dict[str, Any]]]:
        """List candidates, defaulting to those needing work."""
        try:
            filter_statuses = statuses or [
                "needs_review",
                "review_ready",
                "publish_ready",
            ]
            candidates = self.candidate_repo.get_by_status(
                filter_statuses, limit=limit, offset=offset
            )

            # Enrich with counts and next action hint
            for c in candidates:
                cid = c["candidate_id"]
                c["evidence_count"] = self.evidence_repo.count_for_candidate(cid)

                latest_score = self.score_repo.get_latest_for_candidate(cid)
                if latest_score:
                    c["score_status"] = latest_score["status"]
                    c["latest_score"] = latest_score["computed_score"]
                else:
                    c["score_status"] = "unscored"
                    c["latest_score"] = None

                if c["status"] == "needs_review":
                    c["next_action"] = "Review and score this candidate."
                elif c["status"] == "review_ready":
                    c["next_action"] = "Approve score to mark publish_ready."
                else:
                    c["next_action"] = "Candidate is ready for issue inclusion."

            return ResultEnvelope(ok=True, data=candidates)
        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "LIST_CANDIDATES_FAILED",
                        "message": str(e),
                        "retryable": True,
                    }
                ],
            )

    def get_candidate(self, candidate_id: str) -> ResultEnvelope[dict[str, Any]]:
        """Get full candidate detail with evidence and lineage."""
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
                            "next_action": "Call radar_list_candidates to see available IDs.",
                        }
                    ],
                )

            data = self.candidate_repo.get_detail(candidate_id)

            return ResultEnvelope(ok=True, data=data)
        except Exception as e:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "GET_CANDIDATE_FAILED",
                        "message": str(e),
                        "retryable": True,
                    }
                ],
            )
