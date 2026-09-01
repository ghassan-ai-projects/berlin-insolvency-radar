"""Enrichment repositories: enrichment summaries and source-normalized claims."""

import uuid
from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.clock import utc_now_iso
from biradar.storage.rows import rows_as_dicts, single_row_as_dict


class EnrichmentRepository(BaseRepository):
    """Repository for enrichment data persistence."""

    def save_enrichment(
        self,
        candidate_id: str,
        sector: str | None = None,
        employee_count_range: str | None = None,
        funding_info: str | None = None,
        tech_stack: str | None = None,
        website_url: str | None = None,
        website_status: str | None = None,
        github_org: str | None = None,
        patent_count: int = 0,
    ) -> str:
        """Insert an enrichment record and return its ID."""
        enrichment_id = f"enrich_{uuid.uuid4().hex}"

        self.db.conn.execute(
            """
            INSERT INTO enrichments
            (id, candidate_id, sector, employee_count_range, funding_info,
             tech_stack, website_url, website_status, github_org,
             patent_count, enriched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                enrichment_id,
                candidate_id,
                sector,
                employee_count_range,
                funding_info,
                tech_stack,
                website_url,
                str(website_status) if website_status else None,
                github_org,
                patent_count,
                utc_now_iso(),
            ],
        )
        return enrichment_id

    def get_enrichment(self, candidate_id: str) -> dict[str, Any] | None:
        """Get the most recent enrichment for a candidate."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM enrichments
            WHERE candidate_id = ?
            ORDER BY enriched_at DESC LIMIT 1
            """,
            [candidate_id],
        )
        return single_row_as_dict(cursor)


class EnrichmentClaimRepository(BaseRepository):
    """Repository for source-normalized enrichment claims."""

    def insert_claim(
        self,
        claim_id: str,
        candidate_id: str,
        source_provider: str,
        source_url: str | None,
        retrieved_at: str,
        field: str,
        value: str,
        classification: str | None,
        note: str | None,
        content_hash: str,
    ) -> str:
        """Insert an enrichment claim if absent and return its ID."""
        existing_id = self._find_existing_claim_id(candidate_id, field, content_hash)
        if existing_id is not None:
            return existing_id

        self.db.conn.execute(
            """
            INSERT INTO enrichment_claims
            (claim_id, candidate_id, source_provider, source_url, retrieved_at,
             field, value, classification, note, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(claim_id) DO NOTHING
            """,
            [
                claim_id,
                candidate_id,
                source_provider,
                source_url,
                retrieved_at,
                field,
                value,
                classification,
                note,
                content_hash,
            ],
        )
        return claim_id

    def _find_existing_claim_id(
        self, candidate_id: str, field: str, content_hash: str
    ) -> str | None:
        """Return the ID of a stored claim with the same candidate and content hash."""
        row = self.db.conn.execute(
            """
            SELECT claim_id FROM enrichment_claims
            WHERE candidate_id = ? AND field = ? AND content_hash = ?
            LIMIT 1
            """,
            [candidate_id, field, content_hash],
        ).fetchone()
        return row[0] if row else None

    def get_for_candidate(self, candidate_id: str) -> list[dict[str, Any]]:
        """Get persisted enrichment claims for a candidate."""
        cursor = self.db.conn.execute(
            """
            SELECT * FROM enrichment_claims
            WHERE candidate_id = ?
            ORDER BY retrieved_at DESC, source_provider ASC, field ASC
            """,
            [candidate_id],
        )
        return rows_as_dicts(cursor)

    def count_for_candidate(self, candidate_id: str) -> int:
        """Count persisted enrichment claims for a candidate."""
        row = self.db.conn.execute(
            "SELECT COUNT(*) FROM enrichment_claims WHERE candidate_id = ?",
            [candidate_id],
        ).fetchone()
        return int(row[0]) if row else 0
