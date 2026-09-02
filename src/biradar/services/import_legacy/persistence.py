"""Transactional persistence of legacy filing rows.

Repository calls only — the caller owns the open transaction; no SQL here.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from biradar.domain.dedupe import compute_dedupe_key
from biradar.services.import_legacy.classification import (
    classify_candidate,
    is_compliant,
    is_malformed,
    malformed_warning,
)
from biradar.services.import_legacy.rows import FilingRow, extract_filing_row
from biradar.storage.db import compute_content_hash
from biradar.storage.repository import (
    CandidateRepository,
    EvidenceRepository,
    RawRecordRepository,
)

_DUPLICATE_MATCH_REASON = "duplicate_import_from_legacy"
_IMPORT_MATCH_REASON = "direct_import_from_legacy"
_EVIDENCE_FIELDS = ("company_name", "court", "case_number")


@dataclass(frozen=True)
class ImportOutcome:
    """Counters and warnings produced by one real-import pass."""

    inserted_candidates: int
    duplicates: int
    rejected: int
    warnings: list[str]


def persist_import_rows(
    filings: list[dict[str, Any]],
    raw_repo: RawRecordRepository,
    candidate_repo: CandidateRepository,
    evidence_repo: EvidenceRepository,
    source_run_id: str,
) -> ImportOutcome:
    """Write every importable filing inside the caller's transaction."""
    inserted = 0
    duplicates = 0
    rejected = 0
    warnings: list[str] = []
    imported_keys: set[str] = set()

    for row_dict in filings:
        row = extract_filing_row(row_dict)
        if not is_compliant(row):
            rejected += 1
            continue

        dedupe_key = compute_dedupe_key(
            row.company_name, row.court, row.case_number, row.publication_date
        )
        candidate_id = f"cand_{dedupe_key}"
        persisted_raw_id = _persist_raw_record(raw_repo, row_dict, row, source_run_id)

        # get_by_id must stay first: it runs on every non-rejected row, and
        # reordering would silently skip the DB read for in-run duplicates.
        if candidate_repo.get_by_id(candidate_id) or dedupe_key in imported_keys:
            duplicates += 1
            _link_duplicate(candidate_repo, candidate_id, persisted_raw_id)
            continue
        imported_keys.add(dedupe_key)

        if is_malformed(row):
            warnings.append(malformed_warning(row.filing_id))
        _insert_new_candidate(
            candidate_repo, evidence_repo, row, candidate_id, persisted_raw_id
        )
        inserted += 1

    return ImportOutcome(
        inserted_candidates=inserted,
        duplicates=duplicates,
        rejected=rejected,
        warnings=warnings,
    )


def _persist_raw_record(
    raw_repo: RawRecordRepository,
    row_dict: dict[str, Any],
    row: FilingRow,
    source_run_id: str,
) -> str:
    """Upsert the raw record even when the candidate turns out duplicate."""
    return raw_repo.upsert_raw_record(
        raw_record_id=f"raw_{uuid.uuid4().hex}",
        source_run_id=source_run_id,
        source_id="legacy_scout",
        external_id=row.filing_id,
        retrieved_at=row.scraped_at,
        source_url=row.source_url or None,
        raw_text=row.raw_text or None,
        raw_json=json.dumps(row_dict),
        content_hash=compute_content_hash(json.dumps(row_dict, sort_keys=True)),
    )


def _link_duplicate(
    candidate_repo: CandidateRepository, candidate_id: str, raw_record_id: str
) -> None:
    candidate_repo.link_to_raw(
        candidate_id=candidate_id,
        raw_record_id=raw_record_id,
        match_confidence=1.0,
        match_reason=_DUPLICATE_MATCH_REASON,
    )


def _insert_new_candidate(
    candidate_repo: CandidateRepository,
    evidence_repo: EvidenceRepository,
    row: FilingRow,
    candidate_id: str,
    raw_record_id: str,
) -> None:
    """Upsert the candidate, link it to its raw record, and add evidence."""
    classification = classify_candidate(row)
    candidate_repo.upsert_candidate(
        candidate_id=candidate_id,
        company_name=row.company_name,
        legal_form=row.legal_form or None,
        court=row.court or None,
        case_number=row.case_number or None,
        register_number=row.register_number or None,
        publication_date=row.publication_date or None,
        publication_type=row.publication_type or None,
        status=classification.status,
        source_quality="C",
        risk_flags=classification.risk_flags,
    )
    candidate_repo.link_to_raw(
        candidate_id=candidate_id,
        raw_record_id=raw_record_id,
        match_confidence=1.0,
        match_reason=_IMPORT_MATCH_REASON,
    )
    _insert_field_evidence(evidence_repo, row, candidate_id)


def _insert_field_evidence(
    evidence_repo: EvidenceRepository,
    row: FilingRow,
    candidate_id: str,
) -> None:
    """Insert one high-confidence evidence item per key field."""
    for field_name in _EVIDENCE_FIELDS:
        value = getattr(row, field_name)
        if not value:
            continue
        evidence_repo.insert_evidence(
            evidence_id=f"ev_{uuid.uuid4().hex}",
            candidate_id=candidate_id,
            source_provider="legacy_scout",
            source_url=row.source_url or None,
            retrieved_at=row.scraped_at,
            field=field_name,
            value=str(value),
            confidence="high",
            trust_level="C",
            snippet=f"Imported: {field_name} = {value}",
            content_hash=compute_content_hash(str(value)),
        )
