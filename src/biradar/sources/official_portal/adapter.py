"""Adapter orchestrating live and fixture fetches from the official portal."""

import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from biradar.sources.official_portal.live_fetch import fetch_live_records
from biradar.sources.official_portal.models import ParsedPortalResponse
from biradar.sources.official_portal.response_parsing import (
    parse_response,
    parse_response_details,
)
from biradar.sources.official_portal.run_bookkeeping import (
    build_run_result,
    complete_source_run,
    persist_records,
)
from biradar.storage.repository import RawRecordRepository, SourceRunRepository

logger = logging.getLogger(__name__)


class OfficialPortalAdapter:
    """Adapter for fetching insolvency records from the official German portal."""

    def __init__(self, db):
        self.source_run_repo = SourceRunRepository(db)
        self.raw_record_repo = RawRecordRepository(db)
        self.source_id = "official_insolvency_portal"

    def _persist_records(
        self,
        source_run_id: str,
        records: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[int, int]:
        """Persist parsed records and attach persisted raw-record IDs."""
        return persist_records(
            self.raw_record_repo, self.source_id, source_run_id, records, dry_run
        )

    def _parse_response(self, html_or_xml: str) -> list[dict[str, Any]]:
        """Parse the portal response into raw record dictionaries."""
        return parse_response(html_or_xml)

    def _parse_response_details(self, html_or_xml: str) -> ParsedPortalResponse:
        """Parse the portal response into records plus parser metadata."""
        return parse_response_details(html_or_xml)

    def fetch_fixture_date_range(
        self,
        fixture_path: str,
        start_date: date,
        end_date: date,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Fetch records from a saved fixture while preserving source-run behavior."""
        source_run_id = str(uuid.uuid4())
        errors: list[str] = []
        records: list[dict[str, Any]] = []
        records_seen = 0
        records_imported = 0

        if not dry_run:
            self.source_run_repo.create_run(
                source_run_id=source_run_id,
                source_id=self.source_id,
                run_type="fixture_scrape",
                params_json=f'{{"start_date": "{start_date.isoformat()}", "end_date": "{end_date.isoformat()}", "fixture_path": "{fixture_path}"}}',
            )

        try:
            html_or_xml = Path(fixture_path).read_text(encoding="utf-8")
            records = parse_response(html_or_xml)
            records_seen, records_imported = self._persist_records(
                source_run_id, records, dry_run
            )
        except Exception as exc:
            errors.append(str(exc))

        if not dry_run:
            complete_source_run(
                self.source_run_repo,
                source_run_id,
                records_seen,
                records_imported,
                errors,
            )
        return build_run_result(
            source_run_id, records, errors, records_seen, records_imported
        )

    async def fetch_date_range(
        self, start_date: date, end_date: date, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Fetch records for a given date range.

        Args:
            start_date: Start of the date range.
            end_date: End of the date range.
            dry_run: If True, do not persist any records.

        Returns:
            Summary of the fetch operation.
        """
        source_run_id = str(uuid.uuid4())

        logger.info(
            "Starting official portal fetch",
            extra={
                "source_run_id": source_run_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "dry_run": dry_run,
            },
        )

        if not dry_run:
            self.source_run_repo.create_run(
                source_run_id=source_run_id,
                source_id=self.source_id,
                run_type="scheduled_scrape",
                params_json=f'{{"start_date": "{start_date.isoformat()}", "end_date": "{end_date.isoformat()}"}}',
            )

        records, records_seen, records_imported, errors = await fetch_live_records(
            self.raw_record_repo,
            self.source_id,
            source_run_id,
            start_date,
            end_date,
            dry_run,
        )

        if not dry_run:
            complete_source_run(
                self.source_run_repo,
                source_run_id,
                records_seen,
                records_imported,
                errors,
            )

        logger.info(
            "Official portal fetch completed",
            extra={
                "source_run_id": source_run_id,
                "status": "completed" if not errors else "failed",
                "records_seen": records_seen,
                "records_imported": records_imported,
            },
        )

        return build_run_result(
            source_run_id, records, errors, records_seen, records_imported
        )
