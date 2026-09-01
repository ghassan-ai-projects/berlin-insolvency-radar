"""Source run repository: scrape-run lifecycle, history, and coverage lookup."""

import json
from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import rows_as_dicts, single_row_as_dict


def _run_filters(source_id: str | None, status: str | None) -> tuple[str, list[Any]]:
    """Build the WHERE fragment and parameters for optional run filters."""
    fragment = ""
    params: list[Any] = []
    if source_id:
        fragment += " AND source_id = ?"
        params.append(source_id)
    if status:
        fragment += " AND status = ?"
        params.append(status)
    return fragment, params


def _parse_run_window(params_json: str | None) -> tuple[str, str] | None:
    """Parse a run's stored date window; None when absent, empty, or malformed."""
    if not params_json:
        return None
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        return None
    run_start = params.get("start_date")
    run_end = params.get("end_date")
    if not run_start or not run_end:
        return None
    return run_start, run_end


class SourceRunRepository(BaseRepository):
    """Handles source run record operations."""

    def get_latest_run(self, source_id: str) -> dict[str, Any] | None:
        """Get the most recent source run."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM source_runs
            WHERE source_id = ?
            ORDER BY started_at DESC LIMIT 1
            """,
            [source_id],
        )
        return single_row_as_dict(cursor)

    def get_latest_successful_run(self) -> dict[str, Any] | None:
        """Get the most recent successful source run across all sources."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM source_runs
            WHERE status = 'success'
            ORDER BY completed_at DESC, started_at DESC LIMIT 1
            """
        )
        return single_row_as_dict(cursor)

    def find_covering_run(
        self,
        source_id: str,
        start_date: str,
        end_date: str,
    ) -> str | None:
        """Return source_run_id of a completed run whose date window covers the
        requested range. Returns None if no covering run exists."""
        cursor = self.db.conn.execute(
            """
            SELECT source_run_id, params_json FROM source_runs
            WHERE source_id = ? AND status IN ('completed', 'success')
            ORDER BY completed_at DESC
            """,
            [source_id],
        )
        for run_id, params_json in cursor.fetchall():
            window = _parse_run_window(params_json)
            if window is None:
                continue
            run_start, run_end = window
            if run_start <= start_date and run_end >= end_date:
                return run_id
        return None

    def list_runs(
        self,
        source_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List source runs with optional source/status filters."""
        filters, filter_params = _run_filters(source_id, status)
        query = (
            "SELECT * FROM source_runs WHERE 1=1"
            f"{filters} ORDER BY started_at DESC LIMIT ?"
        )
        cursor = self.db.conn.execute(query, [*filter_params, limit])
        return rows_as_dicts(cursor)

    def create_run(
        self,
        source_run_id: str,
        source_id: str,
        run_type: str,
        params_json: str | None = None,
    ) -> None:
        """Create a new source run."""
        self.db.conn.execute(
            """
            INSERT INTO source_runs
            (source_run_id, source_id, run_type, status, started_at, params_json)
            VALUES (?, ?, ?, 'running', ?, ?)
            """,
            [source_run_id, source_id, run_type, utc_now_iso(), params_json],
        )

    def complete_run(
        self,
        source_run_id: str,
        records_seen: int,
        records_imported: int,
        duplicates: int,
        rejected: int,
        error_json: str | None = None,
    ) -> None:
        """Mark a source run as completed or failed."""
        status = "failed" if error_json else "completed"
        self.db.conn.execute(
            """
            UPDATE source_runs
            SET status = ?, completed_at = ?, records_seen = ?, records_imported = ?, duplicates = ?, rejected = ?, error_json = ?
            WHERE source_run_id = ?
            """,
            [
                status,
                utc_now_iso(),
                records_seen,
                records_imported,
                duplicates,
                rejected,
                error_json,
                source_run_id,
            ],
        )
