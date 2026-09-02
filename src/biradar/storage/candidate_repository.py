"""Candidate repository: candidate rows, status changes, and detail assembly."""

import json
from typing import Any

from biradar.domain.validation import validate_date_field
from biradar.storage.audit_repository import AuditRepository
from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.enrichment_repository import (
    EnrichmentClaimRepository,
    EnrichmentRepository,
)
from biradar.storage.evidence_repository import EvidenceRepository
from biradar.storage.raw_record_repository import RawRecordRepository
from biradar.storage.review_repository import ReviewRepository
from biradar.storage.rows import rows_as_dicts, single_row_as_dict
from biradar.storage.score_repository import ScoreRepository


class CandidateRepository(BaseRepository):
    """Handles candidate entity operations."""

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
        cursor = self.db.conn.execute(query, statuses + [limit, offset])
        return rows_as_dicts(cursor)

    def get_by_id(self, candidate_id: str) -> dict[str, Any] | None:
        """Get a single candidate by ID with basic info."""
        cursor = self.db.conn.execute(
            "SELECT * FROM candidates WHERE candidate_id = ? LIMIT 1", [candidate_id]
        )
        return single_row_as_dict(cursor)

    def get_detail(self, candidate_id: str) -> dict[str, Any] | None:
        """Get candidate detail with evidence, scores, reviews, source, and audit lineage."""
        candidate = self.get_by_id(candidate_id)
        if not candidate:
            return None
        return {
            "candidate": candidate,
            **self._related_candidate_records(candidate_id),
        }

    def _related_candidate_records(self, candidate_id: str) -> dict[str, Any]:
        """Gather the evidence, scores, reviews, lineage, and audit trail of a candidate."""
        return {
            "evidence": EvidenceRepository(self.db).get_for_candidate(candidate_id),
            "scores": ScoreRepository(self.db).get_for_candidate(candidate_id),
            "reviews": ReviewRepository(self.db).get_for_candidate(candidate_id),
            "source_lineage": RawRecordRepository(self.db).get_for_candidate(
                candidate_id
            ),
            "enrichment_summary": EnrichmentRepository(self.db).get_enrichment(
                candidate_id
            ),
            "enrichment_claims": EnrichmentClaimRepository(self.db).get_for_candidate(
                candidate_id
            ),
            "audit_events": AuditRepository(self.db).get_events(
                entity_type="candidate", entity_id=candidate_id, limit=100
            ),
        }

    def update_status(self, candidate_id: str, new_status: str) -> None:
        """Update candidate status."""
        self.db.conn.execute(
            """
            UPDATE candidates
            SET status = ?, updated_at = ?
            WHERE candidate_id = ?
            """,
            [new_status, utc_now_iso(), candidate_id],
        )

    def get_counts_by_status(self) -> dict[str, int]:
        """Get counts of candidates grouped by status."""
        cursor = self.db.conn.execute(
            "SELECT status, COUNT(*) FROM candidates GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def upsert_candidate(
        self,
        candidate_id: str,
        company_name: str,
        legal_form: str | None,
        court: str | None,
        case_number: str | None,
        register_number: str | None,
        publication_date: str | None,
        publication_type: str | None,
        status: str,
        source_quality: str | None = None,
        risk_flags: list[str] | None = None,
    ) -> None:
        """Upsert candidate by ID."""
        now = utc_now_iso()
        risk_flags_json = json.dumps(risk_flags) if risk_flags else None
        validated_pub_date = validate_date_field(publication_date)

        self.db.conn.execute(
            """
            INSERT INTO candidates
            (candidate_id, canonical_company_name, legal_form, court, case_number,
             register_number, publication_date, publication_type, status, source_quality, risk_flags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
            """,
            [
                candidate_id,
                company_name,
                legal_form,
                court,
                case_number,
                register_number,
                validated_pub_date,
                publication_type,
                status,
                source_quality,
                risk_flags_json,
                now,
                now,
            ],
        )

    def link_to_raw(
        self,
        candidate_id: str,
        raw_record_id: str,
        match_confidence: float,
        match_reason: str,
    ) -> None:
        """Link candidate to a raw source record."""
        self.db.conn.execute(
            """
            INSERT INTO candidate_sources (candidate_id, raw_record_id, match_confidence, match_reason)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(candidate_id, raw_record_id) DO NOTHING
            """,
            [candidate_id, raw_record_id, match_confidence, match_reason],
        )

    def find_raw_ids_with_candidates(self, raw_ids: list[str]) -> list[str]:
        """Return the raw record IDs that already have a linked candidate."""
        if not raw_ids:
            return []
        placeholders = ",".join("?" * len(raw_ids))
        rows = self.db.conn.execute(
            f"SELECT DISTINCT raw_record_id FROM candidate_sources WHERE raw_record_id IN ({placeholders})",
            raw_ids,
        ).fetchall()
        return [row[0] for row in rows]
