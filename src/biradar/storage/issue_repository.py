"""Issue repository: newsletter issue drafts and their candidate links."""

from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import single_row_as_dict


class IssueRepository(BaseRepository):
    """Handles issue draft operations."""

    def create_issue(
        self,
        issue_id: str,
        week: str,
        tier: str,
        title: str,
        draft_markdown: str,
        created_by: str,
    ) -> None:
        """Create an issue draft."""
        self.db.conn.execute(
            """
            INSERT INTO issues
            (issue_id, week, tier, status, title, draft_markdown, created_by, created_at)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            [issue_id, week, tier, title, draft_markdown, created_by, utc_now_iso()],
        )

    def link_candidate(
        self,
        issue_id: str,
        candidate_id: str,
        rank: int,
        section: str,
        included_score_id: str | None,
    ) -> None:
        """Link a candidate to an issue."""
        self.db.conn.execute(
            """
            INSERT INTO issue_candidates (issue_id, candidate_id, rank, section, included_score_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(issue_id, candidate_id) DO NOTHING
            """,
            [issue_id, candidate_id, rank, section, included_score_id],
        )

    def mark_exported(self, issue_id: str, export_path: str) -> None:
        """Mark an issue as exported."""
        self.db.conn.execute(
            "UPDATE issues SET status = 'exported', exported_at = ?, export_path = ? WHERE issue_id = ?",
            [utc_now_iso(), export_path, issue_id],
        )

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Get a single issue by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM issues WHERE issue_id = ? LIMIT 1", [issue_id]
        )
        return single_row_as_dict(cursor)
