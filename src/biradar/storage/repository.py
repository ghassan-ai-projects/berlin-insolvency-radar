"""Repository layer for database operations. Centralizes all DuckDB access."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from biradar.storage.db import Database


class AuditRepository:
    """Handles append-only audit event writes."""

    def __init__(self, db: Database):
        self.db = db

    def log_event(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        request_data: dict[str, Any] | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> str:
        """Log an audit event and return the audit_id."""
        audit_id = f"audit_{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()

        request_json = json.dumps(request_data) if request_data else None
        result_json = json.dumps(result_data) if result_data else None

        self.db.conn.execute(
            """
            INSERT INTO audit_events 
            (audit_id, actor, action, entity_type, entity_id, request_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                audit_id,
                actor,
                action,
                entity_type,
                entity_id,
                request_json,
                result_json,
                now,
            ],
        )
        return audit_id

    def get_events(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve audit events with optional filters."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        if actor:
            query += " AND actor = ?"
            params.append(actor)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class CandidateRepository:
    """Handles candidate entity operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_by_status(
        self, statuses: list[str], limit: int = 25, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get candidates filtered by status, ordered by creation date."""
        placeholders = ", ".join(["?"] * len(statuses))
        query = f"""
            SELECT candidate_id, canonical_company_name, legal_form, court, case_number, 
                   publication_date, status, source_quality, risk_flags_json, created_at
            FROM candidates
            WHERE status IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params = statuses + [limit, offset]
        cursor = self.db.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        """Get a single candidate by ID with basic info."""
        cursor = self.db.conn.execute(
            "SELECT * FROM candidates WHERE candidate_id = ? LIMIT 1", [candidate_id]
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    def update_status(self, candidate_id: str, new_status: str) -> None:
        """Update candidate status."""
        now = datetime.now(UTC).isoformat()
        self.db.conn.execute(
            """
            UPDATE candidates 
            SET status = ?, updated_at = ? 
            WHERE candidate_id = ?
            """,
            [new_status, now, candidate_id],
        )

    def get_counts_by_status(self) -> dict[str, int]:
        """Get counts of candidates grouped by status."""
        cursor = self.db.conn.execute(
            "SELECT status, COUNT(*) FROM candidates GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


class SourceRunRepository:
    """Handles source run record operations."""

    def __init__(self, db: Database):
        self.db = db

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
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
