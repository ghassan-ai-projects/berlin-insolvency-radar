"""Candidate service for querying and listing candidates."""

from typing import Any

from biradar.mcp.envelope import ResultEnvelope
from biradar.storage.db import Database
from biradar.storage.repository import CandidateRepository


class CandidateService:
    def __init__(self, db: Database):
        self.db = db
        self.repo = CandidateRepository(db)

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
            candidates = self.repo.get_by_status(
                filter_statuses, limit=limit, offset=offset
            )

            # Enrich with next action hint
            for c in candidates:
                if c["status"] == "needs_review":
                    c["next_action"] = "Review and score this candidate."
                elif c["status"] == "review_ready":
                    c["next_action"] = "Approve score to mark publish_ready."

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
            candidate = self.repo.get_by_id(candidate_id)
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

            # Fetch evidence
            evidence_cursor = self.db.conn.execute(
                "SELECT * FROM evidence_items WHERE candidate_id = ?", [candidate_id]
            )
            evidence_cols = [desc[0] for desc in evidence_cursor.description]
            evidence = [
                dict(zip(evidence_cols, row)) for row in evidence_cursor.fetchall()
            ]

            # Fetch scores
            score_cursor = self.db.conn.execute(
                "SELECT * FROM scores WHERE candidate_id = ? ORDER BY created_at DESC",
                [candidate_id],
            )
            score_cols = [desc[0] for desc in score_cursor.description]
            scores = [dict(zip(score_cols, row)) for row in score_cursor.fetchall()]

            # Fetch reviews
            review_cursor = self.db.conn.execute(
                "SELECT * FROM reviews WHERE candidate_id = ? ORDER BY created_at DESC",
                [candidate_id],
            )
            review_cols = [desc[0] for desc in review_cursor.description]
            reviews = [dict(zip(review_cols, row)) for row in review_cursor.fetchall()]

            data = {
                "candidate": candidate,
                "evidence": evidence,
                "scores": scores,
                "reviews": reviews,
            }

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
