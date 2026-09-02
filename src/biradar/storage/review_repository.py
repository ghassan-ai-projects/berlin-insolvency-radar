"""Review repository: human review decisions on candidates."""

from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import rows_as_dicts


class ReviewRepository(BaseRepository):
    """Handles review record operations."""

    def insert_review(
        self,
        review_id: str,
        candidate_id: str,
        reviewer: str,
        decision: str,
        from_status: str,
        to_status: str,
        note: str | None,
    ) -> None:
        """Insert a review record."""
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
                from_status,
                to_status,
                note,
                utc_now_iso(),
            ],
        )

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get reviews for a candidate."""
        cursor = self.db.conn.execute(
            "SELECT * FROM reviews WHERE candidate_id = ? ORDER BY created_at DESC",
            [candidate_id],
        )
        return rows_as_dicts(cursor)
