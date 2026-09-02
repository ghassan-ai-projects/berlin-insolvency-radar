"""Source-run bookkeeping: persistence of fetched records and run completion."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any


def persist_records(
    raw_record_repo,
    source_id: str,
    source_run_id: str,
    records: list[dict[str, Any]],
    dry_run: bool,
) -> tuple[int, int]:
    """Persist parsed records and attach persisted raw-record IDs."""
    records_seen = len(records)
    records_imported = 0
    for record in records:
        raw_text = record.get("raw_text", "")
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        raw_record_id = f"raw_{uuid.uuid4().hex}"
        retrieved_at = datetime.now(UTC).isoformat()
        if not dry_run:
            persisted_raw_record_id = raw_record_repo.upsert_raw_record(
                raw_record_id=raw_record_id,
                source_run_id=source_run_id,
                source_id=source_id,
                external_id=record.get("external_id"),
                retrieved_at=retrieved_at,
                source_url=record.get("source_url"),
                raw_text=raw_text,
                raw_json=None,
                content_hash=content_hash,
                parser_version="v1",
            )
            record["raw_record_id"] = persisted_raw_record_id
        records_imported += 1
    return records_seen, records_imported


def complete_source_run(
    source_run_repo,
    source_run_id: str,
    records_seen: int,
    records_imported: int,
    errors: list[str],
    duplicates: int = 0,
    rejected: int = 0,
) -> None:
    """Close the source run as completed or failed based on the errors."""
    source_run_repo.complete_run(
        source_run_id=source_run_id,
        records_seen=records_seen,
        records_imported=records_imported,
        duplicates=duplicates,
        rejected=rejected,
        error_json=json.dumps(errors) if errors else None,
    )


def build_run_result(
    source_run_id: str,
    records: list[dict[str, Any]],
    errors: list[str],
    records_seen: int,
    records_imported: int,
    duplicates: int = 0,
    rejected: int = 0,
) -> dict[str, Any]:
    """Build the fetch summary dict consumed by the pipeline acquisition."""
    return {
        "source_run_id": source_run_id,
        "status": "completed" if not errors else "failed",
        "records_seen": records_seen,
        "records_imported": records_imported,
        "duplicates": duplicates,
        "rejected": rejected,
        "errors": errors,
        "records": records,
    }
