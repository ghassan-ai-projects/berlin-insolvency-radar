"""Read-only dry-run accounting for the legacy import."""

from pathlib import Path
from typing import Any

from biradar.domain.dedupe import compute_dedupe_key
from biradar.mcp.envelope import ResultEnvelope
from biradar.services.import_legacy.classification import (
    is_compliant,
    is_malformed,
    malformed_warning,
)
from biradar.services.import_legacy.integrity import (
    FileFingerprint,
    snapshot_unchanged,
)
from biradar.services.import_legacy.rows import extract_filing_row
from biradar.storage.repository import CandidateRepository

_DRY_RUN_NOTICE = "Dry run complete. No data was persisted."


def run_dry_run(
    filings: list[dict[str, Any]],
    candidate_repo: CandidateRepository,
    legacy_path: Path,
    pre_fingerprint: FileFingerprint,
) -> ResultEnvelope[dict[str, Any]]:
    """Count what a real import would do without persisting anything."""
    would_import = 0
    duplicates = 0
    rejected = 0
    seen_keys: set[str] = set()
    warnings: list[str] = []

    for row_dict in filings:
        row = extract_filing_row(row_dict)
        if not is_compliant(row):
            rejected += 1
            continue

        dedupe_key = compute_dedupe_key(
            row.company_name, row.court, row.case_number, row.publication_date
        )
        if dedupe_key in seen_keys or candidate_repo.get_by_id(f"cand_{dedupe_key}"):
            duplicates += 1
            continue
        seen_keys.add(dedupe_key)
        would_import += 1

        if is_malformed(row):
            warnings.append(malformed_warning(row_dict.get("filing_id")))

    if not snapshot_unchanged(legacy_path, pre_fingerprint):
        return ResultEnvelope(
            ok=False,
            errors=[
                {
                    "code": "LEGACY_MUTATED",
                    "message": "Legacy database changed during dry-run import.",
                    "retryable": False,
                }
            ],
        )

    return ResultEnvelope(
        ok=True,
        data={
            "dry_run": True,
            "raw_records_seen": len(filings),
            "distinct_candidates": would_import,
            "would_import": would_import,
            "duplicates": duplicates,
            "rejected": rejected,
            "warnings": warnings + [_DRY_RUN_NOTICE],
        },
        next_action="Remove dry_run=true to execute the import.",
    )
