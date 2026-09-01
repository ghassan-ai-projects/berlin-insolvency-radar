"""Unit tests for the legacy import support modules."""

import os
from datetime import datetime

import pytest

from biradar.domain.dedupe import compute_dedupe_key
from biradar.services.import_legacy.classification import (
    classify_candidate,
    is_compliant,
    is_malformed,
    malformed_warning,
)
from biradar.services.import_legacy.dry_run import run_dry_run
from biradar.services.import_legacy.integrity import (
    LegacyIntegrityError,
    fingerprint_file,
    snapshot_unchanged,
    verify_import_snapshot,
)
from biradar.services.import_legacy.rows import FilingRow, extract_filing_row


def _row(**overrides) -> FilingRow:
    values = {
        "company_name": "Muster GmbH",
        "legal_form": "GmbH",
        "raw_text": "Insolvenzverfahren eroeffnet",
        "court": "AG Charlottenburg",
        "case_number": "34 IN 123/24",
        "publication_date": "2024-05-01",
        "publication_type": "Insolvenzgerichtliche Mitteilung",
        "register_number": "HRB 99",
        "source_url": "https://example.test/insolvency",
        "filing_id": "leg_1",
        "scraped_at": "2024-05-02T00:00:00+00:00",
    }
    values.update(overrides)
    return FilingRow(**values)


class _StubCandidateRepo:
    """Stand-in for CandidateRepository answering get_by_id lookups."""

    def __init__(self, existing_ids=()):
        self._existing_ids = set(existing_ids)

    def get_by_id(self, candidate_id):
        if candidate_id in self._existing_ids:
            return {"candidate_id": candidate_id}
        return None


def test_extract_filing_row_coerces_values_to_strings():
    row = extract_filing_row(
        {
            "company_name": "Muster GmbH",
            "legal_form": "GmbH",
            "raw_text": "text",
            "court": "AG Charlottenburg",
            "case_number": 123,
            "publication_date": "2024-05-01",
            "publication_type": None,
            "register_number": "HRB 99",
            "source_url": "https://example.test",
            "filing_id": "leg_1",
            "scraped_at": "2024-05-02T00:00:00+00:00",
        }
    )

    assert row.case_number == "123"
    assert row.publication_type == ""
    assert row.company_name == "Muster GmbH"


def test_extract_filing_row_defaults_missing_filing_id_and_scraped_at():
    row = extract_filing_row({})

    assert row.filing_id.startswith("leg_")
    assert row.company_name == ""
    assert row.court == ""
    datetime.fromisoformat(row.scraped_at)


def test_is_compliant_accepts_allowed_corporate_form():
    assert is_compliant(_row()) is True


def test_is_compliant_rejects_consumer_indicator_in_raw_text():
    assert is_compliant(_row(raw_text="Privatinsolvenz des Inhabers")) is False


def test_is_compliant_rejects_unsupported_legal_form():
    assert is_compliant(_row(legal_form="e.K.")) is False


def test_is_malformed_detects_missing_core_fields():
    assert is_malformed(_row(court="")) is True
    assert is_malformed(_row(case_number="")) is True
    assert is_malformed(_row(publication_date="")) is True
    assert is_malformed(_row()) is False


def test_classify_candidate_returns_review_ready_for_complete_row():
    classification = classify_candidate(_row())

    assert classification.status == "review_ready"
    assert classification.risk_flags == []


def test_classify_candidate_flags_malformed_source_row():
    classification = classify_candidate(_row(court=""))

    assert classification.status == "needs_review"
    assert classification.risk_flags == ["malformed_source_row"]


def test_classify_candidate_flags_missing_legal_form():
    classification = classify_candidate(_row(legal_form=""))

    assert classification.status == "needs_review"
    assert classification.risk_flags == ["missing_legal_form"]


def test_classify_candidate_flags_whitespace_legal_form_as_missing():
    classification = classify_candidate(_row(legal_form="   "))

    assert classification.risk_flags == ["missing_legal_form"]


def test_malformed_warning_renders_filing_label():
    assert malformed_warning("leg_1") == (
        "Malformed row leg_1: missing court, case number, or publication date."
    )
    assert malformed_warning(None) == (
        "Malformed row None: missing court, case number, or publication date."
    )


def test_fingerprint_file_is_stable_for_unchanged_file(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")

    assert fingerprint_file(path) == fingerprint_file(path)


def test_fingerprint_file_changes_when_content_changes(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)

    path.write_bytes(b"filings mutated")

    assert fingerprint_file(path) != pre


def test_snapshot_unchanged_reflects_file_mutation(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)

    assert snapshot_unchanged(path, pre) is True

    path.write_bytes(b"filings mutated")

    assert snapshot_unchanged(path, pre) is False


def test_verify_import_snapshot_passes_for_unchanged_file(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)

    verify_import_snapshot(path, pre)


def test_verify_import_snapshot_raises_mutated_on_metadata_change(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)
    path.write_bytes(b"filings mutated")

    with pytest.raises(LegacyIntegrityError) as excinfo:
        verify_import_snapshot(path, pre)

    assert excinfo.value.code == "LEGACY_MUTATED"
    assert str(excinfo.value) == "Legacy database was modified during import."


def test_verify_import_snapshot_raises_hash_mismatch_for_same_metadata(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"AAAAAA")
    stat_before = path.stat()
    pre = fingerprint_file(path)
    path.write_bytes(b"BBBBBB")
    os.utime(path, ns=(stat_before.st_atime_ns, stat_before.st_mtime_ns))

    with pytest.raises(LegacyIntegrityError) as excinfo:
        verify_import_snapshot(path, pre)

    assert excinfo.value.code == "LEGACY_HASH_MISMATCH"
    assert str(excinfo.value) == "Legacy database content hash changed during import."


def test_legacy_integrity_error_carries_code_and_message():
    error = LegacyIntegrityError("LEGACY_MUTATED", "changed")

    assert error.code == "LEGACY_MUTATED"
    assert str(error) == "changed"


def test_run_dry_run_counts_and_warns_without_persisting(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)
    base_row = {
        "company_name": "Muster GmbH",
        "legal_form": "GmbH",
        "raw_text": "ok",
        "court": "AG Charlottenburg",
        "case_number": "34 IN 1",
        "publication_date": "2024-05-01",
    }
    filings = [
        {**base_row, "filing_id": "leg_1"},
        {**base_row, "filing_id": "leg_2"},
        {
            "company_name": "Zweite GmbH",
            "legal_form": "GmbH",
            "raw_text": "ok",
            "court": "",
            "case_number": "",
            "publication_date": "",
        },
        {
            "company_name": "Hans E.K.",
            "legal_form": "e.K.",
            "raw_text": "",
            "court": "AG Mitte",
            "case_number": "31 IN 2",
            "publication_date": "2024-05-02",
        },
    ]

    envelope = run_dry_run(filings, _StubCandidateRepo(), path, pre)

    assert envelope.ok is True
    assert envelope.data == {
        "dry_run": True,
        "raw_records_seen": 4,
        "distinct_candidates": 2,
        "would_import": 2,
        "duplicates": 1,
        "rejected": 1,
        "warnings": [
            "Malformed row None: missing court, case number, or publication date.",
            "Dry run complete. No data was persisted.",
        ],
    }
    assert envelope.next_action == "Remove dry_run=true to execute the import."


def test_run_dry_run_counts_known_candidates_as_duplicates(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    pre = fingerprint_file(path)
    filings = [
        {
            "company_name": "Muster GmbH",
            "legal_form": "GmbH",
            "court": "AG Charlottenburg",
            "case_number": "34 IN 1",
            "publication_date": "2024-05-01",
        }
    ]
    dedupe_key = compute_dedupe_key(
        "Muster GmbH", "AG Charlottenburg", "34 IN 1", "2024-05-01"
    )

    envelope = run_dry_run(
        filings,
        _StubCandidateRepo(existing_ids=[f"cand_{dedupe_key}"]),
        path,
        pre,
    )

    assert envelope.data["duplicates"] == 1
    assert envelope.data["would_import"] == 0


def test_run_dry_run_reports_mutation_when_file_changed(tmp_path):
    path = tmp_path / "legacy.duckdb"
    path.write_bytes(b"filings")
    stale_fingerprint = fingerprint_file(path)
    path.write_bytes(b"filings mutated")

    envelope = run_dry_run([], _StubCandidateRepo(), path, stale_fingerprint)

    assert envelope.ok is False
    assert envelope.errors == [
        {
            "code": "LEGACY_MUTATED",
            "message": "Legacy database changed during dry-run import.",
            "retryable": False,
        }
    ]
    assert envelope.audit_id is None
