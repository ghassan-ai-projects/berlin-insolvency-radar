"""Raw record repository: dedupe-on-write storage of retrieved source records."""

from typing import Any

from biradar.storage.base import BaseRepository
from biradar.storage.rows import rows_as_dicts


class RawRecordRepository(BaseRepository):
    """Handles raw source record operations."""

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
        existing_id = self._find_existing_raw_record_id(
            source_id, external_id, content_hash
        )
        if existing_id is not None:
            return existing_id

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

    def _find_existing_raw_record_id(
        self, source_id: str, external_id: str | None, content_hash: str
    ) -> str | None:
        """Return the ID of an already-stored record, matching external ID first."""
        if external_id:
            found = self._find_raw_record_id_by_external_id(source_id, external_id)
            if found is not None:
                return found
        return self._find_raw_record_id_by_content_hash(source_id, content_hash)

    def _find_raw_record_id_by_external_id(
        self, source_id: str, external_id: str
    ) -> str | None:
        """Return the record ID stored for this source and external ID, if any."""
        row = self.db.conn.execute(
            """
                SELECT raw_record_id FROM raw_records
                WHERE source_id = ? AND external_id = ?
                LIMIT 1
            """,
            [source_id, external_id],
        ).fetchone()
        return row[0] if row else None

    def _find_raw_record_id_by_content_hash(
        self, source_id: str, content_hash: str
    ) -> str | None:
        """Return the record ID stored for this source and content hash, if any."""
        row = self.db.conn.execute(
            """
                SELECT raw_record_id FROM raw_records
                WHERE source_id = ? AND content_hash = ?
                LIMIT 1
            """,
            [source_id, content_hash],
        ).fetchone()
        return row[0] if row else None

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
        return rows_as_dicts(cursor)

    def list_by_source_run(self, source_run_id: str) -> list[dict[str, Any]]:
        """Get all raw records for a source run."""
        cursor = self.db.conn.execute(
            "SELECT * FROM raw_records WHERE source_run_id = ?",
            [source_run_id],
        )
        return rows_as_dicts(cursor)
