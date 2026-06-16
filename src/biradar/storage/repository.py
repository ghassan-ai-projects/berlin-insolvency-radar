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

    def get_detail(self, candidate_id: str) -> dict[str, Any] | None:
        """Get candidate detail with evidence, scores, reviews, source, and audit lineage."""
        candidate = self.get_by_id(candidate_id)
        if not candidate:
            return None

        evidence = EvidenceRepository(self.db).get_for_candidate(candidate_id)
        scores = ScoreRepository(self.db).get_for_candidate(candidate_id)
        reviews = ReviewRepository(self.db).get_for_candidate(candidate_id)
        source_lineage = RawRecordRepository(self.db).get_for_candidate(candidate_id)
        audit_events = AuditRepository(self.db).get_events(
            entity_type="candidate", entity_id=candidate_id, limit=100
        )

        return {
            "candidate": candidate,
            "evidence": evidence,
            "scores": scores,
            "reviews": reviews,
            "source_lineage": source_lineage,
            "audit_events": audit_events,
        }

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
        now = datetime.now(UTC).isoformat()
        risk_flags_json = json.dumps(risk_flags) if risk_flags else None

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
                publication_date,
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


class RawRecordRepository:
    """Handles raw source record operations."""

    def __init__(self, db: Database):
        self.db = db

    def upsert_raw_record(
        self,
        raw_record_id: str,
        source_run_id: str,
        source_id: str,
        external_id: str | None,
        retrieved_at: str,
        source_url: str | None,
        raw_text: str | None,
        raw_json: str | None,
        content_hash: str,
        parser_version: str = "v1",
    ) -> str:
        """Upsert raw record by source identity or content hash and return its ID."""
        existing = None
        if external_id:
            existing = self.db.conn.execute(
                """
                SELECT raw_record_id FROM raw_records
                WHERE source_id = ? AND external_id = ?
                LIMIT 1
                """,
                [source_id, external_id],
            ).fetchone()

        if not existing:
            existing = self.db.conn.execute(
                """
                SELECT raw_record_id FROM raw_records
                WHERE source_id = ? AND content_hash = ?
                LIMIT 1
                """,
                [source_id, content_hash],
            ).fetchone()

        if existing:
            return existing[0]

        self.db.conn.execute(
            """
            INSERT INTO raw_records
            (raw_record_id, source_run_id, source_id, external_id, retrieved_at, source_url, raw_text, raw_json, content_hash, parser_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(raw_record_id) DO NOTHING
            """,
            [
                raw_record_id,
                source_run_id,
                source_id,
                external_id,
                retrieved_at,
                source_url,
                raw_text,
                raw_json,
                content_hash,
                parser_version,
            ],
        )
        return raw_record_id

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get raw source records linked to a candidate."""
        cursor = self.db.conn.execute(
            """
            SELECT r.* FROM raw_records r
            JOIN candidate_sources cs ON r.raw_record_id = cs.raw_record_id
            WHERE cs.candidate_id = ?
            ORDER BY r.retrieved_at DESC
            """,
            [candidate_id],
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


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

    def get_latest_successful_run(self) -> dict[str, Any] | None:
        """Get the most recent successful source run across all sources."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM source_runs
            WHERE status = 'success'
            ORDER BY completed_at DESC, started_at DESC LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    def list_runs(
        self,
        source_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List source runs with optional source/status filters."""
        query = "SELECT * FROM source_runs WHERE 1=1"
        params: list[Any] = []
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.db.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def create_run(
        self,
        source_run_id: str,
        source_id: str,
        run_type: str,
        params_json: str | None = None,
    ) -> None:
        """Create a new source run."""
        now = datetime.now(UTC).isoformat()
        self.db.conn.execute(
            """
            INSERT INTO source_runs
            (source_run_id, source_id, run_type, status, started_at, params_json)
            VALUES (?, ?, ?, 'running', ?, ?)
            """,
            [source_run_id, source_id, run_type, now, params_json],
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
        now = datetime.now(UTC).isoformat()
        status = "failed" if error_json else "success"
        self.db.conn.execute(
            """
            UPDATE source_runs
            SET status = ?, completed_at = ?, records_seen = ?, records_imported = ?, duplicates = ?, rejected = ?, error_json = ?
            WHERE source_run_id = ?
            """,
            [
                status,
                now,
                records_seen,
                records_imported,
                duplicates,
                rejected,
                error_json,
                source_run_id,
            ],
        )


class EvidenceRepository:
    """Handles evidence item operations."""

    def __init__(self, db: Database):
        self.db = db

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
        existing = self.db.conn.execute(
            """
            SELECT evidence_id FROM evidence_items
            WHERE candidate_id = ? AND field = ? AND content_hash = ?
            LIMIT 1
            """,
            [candidate_id, field, content_hash],
        ).fetchone()
        if existing:
            return existing[0]

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

    def get_for_candidate(
        self, candidate_id: str, fields: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get evidence items for a candidate, optionally filtered by field."""
        params: list[Any] = [candidate_id]
        field_clause = ""
        if fields:
            field_clause = " AND field IN (" + ", ".join(["?"] * len(fields)) + ")"
            params.extend(fields)

        cursor = self.db.conn.execute(
            f"""
            SELECT * FROM evidence_items
            WHERE candidate_id = ?{field_clause}
            ORDER BY retrieved_at DESC, field ASC
            """,
            params,
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def count_for_candidate(self, candidate_id: str) -> int:
        """Count evidence items for a candidate."""
        row = self.db.conn.execute(
            "SELECT COUNT(*) FROM evidence_items WHERE candidate_id = ?",
            [candidate_id],
        ).fetchone()
        return int(row[0]) if row else 0


class ReviewRepository:
    """Handles review record operations."""

    def __init__(self, db: Database):
        self.db = db

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
        now = datetime.now(UTC).isoformat()
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
                now,
            ],
        )

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get reviews for a candidate."""
        cursor = self.db.conn.execute(
            "SELECT * FROM reviews WHERE candidate_id = ? ORDER BY created_at DESC",
            [candidate_id],
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class ScoreRepository:
    """Handles score record operations."""

    def __init__(self, db: Database):
        self.db = db

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
        now = datetime.now(UTC).isoformat()
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
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

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
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get all scores for a candidate."""
        cursor = self.db.conn.execute(
            "SELECT * FROM scores WHERE candidate_id = ? ORDER BY created_at DESC",
            [candidate_id],
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class IssueRepository:
    """Handles issue draft operations."""

    def __init__(self, db: Database):
        self.db = db

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
        now = datetime.now(UTC).isoformat()
        self.db.conn.execute(
            """
            INSERT INTO issues
            (issue_id, week, tier, status, title, draft_markdown, created_by, created_at)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            [issue_id, week, tier, title, draft_markdown, created_by, now],
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
        now = datetime.now(UTC).isoformat()
        self.db.conn.execute(
            "UPDATE issues SET status = 'exported', exported_at = ?, export_path = ? WHERE issue_id = ?",
            [now, export_path, issue_id],
        )

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Get a single issue by ID."""
        cursor = self.db.conn.execute(
            "SELECT * FROM issues WHERE issue_id = ? LIMIT 1", [issue_id]
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
