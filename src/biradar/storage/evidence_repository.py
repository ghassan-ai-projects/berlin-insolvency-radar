"""Evidence repository: per-field evidence items attached to candidates."""

from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.rows import rows_as_dicts


def _optional_field_clause(fields: list[str] | None) -> tuple[str, list[str]]:
    """Build an IN-clause fragment and parameters for optional field filtering."""
    if not fields:
        return "", []
    placeholders = ", ".join(["?"] * len(fields))
    return f" AND field IN ({placeholders})", list(fields)


class EvidenceRepository(BaseRepository):
    """Handles evidence item operations."""

    def get_existing_fields(self, candidate_ids: list[str]) -> set[tuple[str, str]]:
        """Return set of (candidate_id, field) pairs that already have evidence."""
        if not candidate_ids:
            return set()
        placeholders = ",".join("?" * len(candidate_ids))
        cursor = self.db.conn.execute(
            f"SELECT DISTINCT candidate_id, field FROM evidence_items WHERE candidate_id IN ({placeholders})",
            candidate_ids,
        )
        return {(row[0], row[1]) for row in cursor.fetchall()}

    def insert_evidence(
        self,
        evidence_id: str,
        candidate_id: str,
        source_provider: str,
        source_url: str | None,
        retrieved_at: str,
        field: str,
        value: str,
        confidence: str,
        trust_level: str,
        snippet: str | None,
        content_hash: str,
    ) -> str:
        """Insert an evidence item if absent and return its ID."""
        existing_id = self._find_existing_evidence_id(candidate_id, field, content_hash)
        if existing_id is not None:
            return existing_id

        self.db.conn.execute(
            """
            INSERT INTO evidence_items
            (evidence_id, candidate_id, source_provider, source_url, retrieved_at, field, value, confidence, trust_level, snippet, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evidence_id) DO NOTHING
            """,
            [
                evidence_id,
                candidate_id,
                source_provider,
                source_url,
                retrieved_at,
                field,
                value,
                confidence,
                trust_level,
                snippet,
                content_hash,
            ],
        )
        return evidence_id

    def _find_existing_evidence_id(
        self, candidate_id: str, field: str, content_hash: str
    ) -> str | None:
        """Return the ID of a stored evidence item with the same content hash."""
        row = self.db.conn.execute(
            """
            SELECT evidence_id FROM evidence_items
            WHERE candidate_id = ? AND field = ? AND content_hash = ?
            LIMIT 1
            """,
            [candidate_id, field, content_hash],
        ).fetchone()
        return row[0] if row else None

    def get_for_candidate(
        self, candidate_id: str, fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get evidence items for a candidate, optionally filtered by field."""
        field_clause, field_params = _optional_field_clause(fields)
        cursor = self.db.conn.execute(
            f"""
            SELECT * FROM evidence_items
            WHERE candidate_id = ?{field_clause}
            ORDER BY retrieved_at DESC, field ASC
            """,
            [candidate_id, *field_params],
        )
        return rows_as_dicts(cursor)

    def count_for_candidate(self, candidate_id: str) -> int:
        """Count evidence items for a candidate."""
        row = self.db.conn.execute(
            "SELECT COUNT(*) FROM evidence_items WHERE candidate_id = ?",
            [candidate_id],
        ).fetchone()
        return int(row[0]) if row else 0
