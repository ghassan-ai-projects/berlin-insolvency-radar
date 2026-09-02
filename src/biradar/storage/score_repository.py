"""Score repository: deterministic opportunity scores per candidate."""

from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import rows_as_dicts, single_row_as_dict


class ScoreRepository(BaseRepository):
    """Handles score record operations."""

    def insert_score(
        self,
        score_id: str,
        candidate_id: str,
        score_version: str,
        company_value: int,
        asset_quality: int,
        sector_attractiveness: int,
        speed_of_action: int,
        legal_risk: int,
        computed_score: float,
        category: str,
        rationale_json: str,
        status: str,
        reviewer: str,
    ) -> None:
        """Insert a score record."""
        now = utc_now_iso()
        approved_at = now if status == "approved" else None
        self.db.conn.execute(
            """
            INSERT INTO scores
            (score_id, candidate_id, score_version, company_value, asset_quality,
             sector_attractiveness, speed_of_action, legal_risk, computed_score, category,
             rationale_json, status, reviewer, created_at, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                score_id,
                candidate_id,
                score_version,
                company_value,
                asset_quality,
                sector_attractiveness,
                speed_of_action,
                legal_risk,
                computed_score,
                category,
                rationale_json,
                status,
                reviewer,
                now,
                approved_at,
            ],
        )

    def get_latest_for_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        """Get latest score for a candidate."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM scores
            WHERE candidate_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [candidate_id],
        )
        return single_row_as_dict(cursor)

    def get_latest_approved_for_candidate(
        self, candidate_id: str
    ) -> dict[str, Any] | None:
        """Get latest approved score for a candidate."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM scores
            WHERE candidate_id = ? AND status = 'approved'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [candidate_id],
        )
        return single_row_as_dict(cursor)

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get all scores for a candidate."""
        cursor = self.db.conn.execute(
            "SELECT * FROM scores WHERE candidate_id = ? ORDER BY created_at DESC",
            [candidate_id],
        )
        return rows_as_dicts(cursor)
