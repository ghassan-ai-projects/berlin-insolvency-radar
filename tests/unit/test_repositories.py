"""Unit tests for the repository modules against a real in-memory DuckDB."""

import pytest

from biradar.storage.audit_repository import AuditRepository
from biradar.storage.candidate_repository import CandidateRepository
from biradar.storage.db import Database
from biradar.storage.enrichment_repository import (
    EnrichmentClaimRepository,
    EnrichmentRepository,
)
from biradar.storage.evidence_repository import EvidenceRepository
from biradar.storage.raw_record_repository import RawRecordRepository
from biradar.storage.source_run_repository import SourceRunRepository


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "repositories.duckdb")
    database.run_migrations()
    try:
        yield database
    finally:
        database.close()


def _create_completed_run(
    db, run_id, params_json, *, error_json=None, source_id="portal"
):
    runs = SourceRunRepository(db)
    runs.create_run(run_id, source_id, "full", params_json)
    runs.complete_run(
        run_id,
        records_seen=1,
        records_imported=1,
        duplicates=0,
        rejected=0,
        error_json=error_json,
    )


def test_get_by_status_returns_only_candidates_in_requested_statuses(db):
    repo = CandidateRepository(db)
    repo.upsert_candidate(
        "cand_a",
        "Firm A",
        "GmbH",
        None,
        None,
        None,
        "2026-01-01",
        "opening",
        "needs_review",
    )
    repo.upsert_candidate(
        "cand_b",
        "Firm B",
        "GmbH",
        None,
        None,
        None,
        "2026-01-02",
        "opening",
        "raw_candidate",
    )

    rows = repo.get_by_status(["needs_review"])

    assert [row["candidate_id"] for row in rows] == ["cand_a"]
    assert rows[0]["canonical_company_name"] == "Firm A"


def test_get_events_filters_by_actor(db):
    audit = AuditRepository(db)
    audit.log_event("agent", "import", "candidate", "cand_1")
    audit.log_event("reviewer", "approve", "candidate", "cand_1")

    rows = audit.get_events(actor="reviewer")

    assert [row["actor"] for row in rows] == ["reviewer"]
    assert rows[0]["action"] == "approve"


def test_get_latest_run_returns_the_most_recently_started_run(db):
    runs = SourceRunRepository(db)
    runs.create_run("run_old", "portal", "full")
    runs.create_run("run_new", "portal", "full")

    latest = runs.get_latest_run("portal")

    assert latest is not None
    assert latest["source_run_id"] == "run_new"
    assert latest["status"] == "running"


def test_get_latest_run_returns_none_for_unknown_source(db):
    assert SourceRunRepository(db).get_latest_run("portal") is None


def test_get_latest_successful_run_prefers_success_over_completed(db):
    _create_completed_run(db, "run_done", None)
    db.conn.execute(
        "INSERT INTO source_runs (source_run_id, source_id, run_type, status, started_at)"
        " VALUES ('run_success', 'portal', 'full', 'success', '2026-01-01T00:00:00+00:00')"
    )

    latest = SourceRunRepository(db).get_latest_successful_run()

    assert latest is not None
    assert latest["source_run_id"] == "run_success"


def test_get_latest_successful_run_returns_none_without_successes(db):
    _create_completed_run(db, "run_done", None)
    assert SourceRunRepository(db).get_latest_successful_run() is None


def test_find_covering_run_skips_runs_with_malformed_params_json(db):
    _create_completed_run(db, "run_bad", "not-json")

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id is None


def test_find_covering_run_skips_non_covering_windows(db):
    _create_completed_run(
        db, "run_far", '{"start_date": "2026-02-01", "end_date": "2026-02-28"}'
    )
    _create_completed_run(
        db, "run_ok", '{"start_date": "2026-01-01", "end_date": "2026-01-31"}'
    )

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id == "run_ok"


def test_find_covering_run_skips_runs_with_missing_window_keys(db):
    _create_completed_run(db, "run_partial", '{"start_date": "2026-01-01"}')

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id is None


def test_find_covering_run_returns_none_when_no_window_covers_the_range(db):
    _create_completed_run(
        db, "run_far", '{"start_date": "2026-02-01", "end_date": "2026-02-28"}'
    )

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id is None


def test_find_covering_run_ignores_runs_that_are_not_completed(db):
    runs = SourceRunRepository(db)
    runs.create_run(
        "run_running",
        "portal",
        "full",
        '{"start_date": "2026-01-01", "end_date": "2026-01-31"}',
    )

    run_id = runs.find_covering_run("portal", "2026-01-05", "2026-01-20")

    assert run_id is None


def test_find_covering_run_returns_none_for_runs_without_params_json(db):
    _create_completed_run(db, "run_empty", None)

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id is None


def test_find_covering_run_only_considers_the_requested_source(db):
    _create_completed_run(
        db,
        "run_other",
        '{"start_date": "2026-01-01", "end_date": "2026-01-31"}',
        source_id="handelsregister",
    )

    run_id = SourceRunRepository(db).find_covering_run(
        "portal", "2026-01-05", "2026-01-20"
    )

    assert run_id is None


def test_list_runs_applies_source_and_status_filters(db):
    runs = SourceRunRepository(db)
    _create_completed_run(db, "run_done", None)
    runs.create_run("run_open", "handelsregister", "full")

    by_source = runs.list_runs(source_id="handelsregister")
    by_status = runs.list_runs(status="running")
    by_both = runs.list_runs(source_id="handelsregister", status="running")

    assert [row["source_run_id"] for row in by_source] == ["run_open"]
    assert [row["source_run_id"] for row in by_status] == ["run_open"]
    assert [row["source_run_id"] for row in by_both] == ["run_open"]


def test_list_runs_orders_most_recent_first_and_honours_limit(db):
    runs = SourceRunRepository(db)
    runs.create_run("run_first", "portal", "full")
    runs.create_run("run_second", "portal", "full")

    rows = runs.list_runs(limit=1)

    assert [row["source_run_id"] for row in rows] == ["run_second"]


def test_find_raw_ids_with_candidates_returns_only_linked_raw_record_ids(db):
    repo = CandidateRepository(db)
    repo.upsert_candidate(
        "cand_1", "Firm A", "GmbH", None, None, None, None, None, "raw_candidate"
    )
    repo.link_to_raw(
        "cand_1", "raw_linked", match_confidence=1.0, match_reason="pipeline_ingest"
    )

    linked = repo.find_raw_ids_with_candidates(["raw_linked", "raw_unlinked"])

    assert linked == ["raw_linked"]


def test_complete_run_marks_the_run_failed_when_an_error_is_present(db):
    runs = SourceRunRepository(db)
    runs.create_run("run_broken", "portal", "full")

    runs.complete_run("run_broken", 3, 1, 1, 1, error_json='{"error": "boom"}')

    row = runs.get_latest_run("portal")
    assert row["status"] == "failed"
    assert row["records_seen"] == 3


def test_complete_run_marks_the_run_completed_without_an_error(db):
    runs = SourceRunRepository(db)
    runs.create_run("run_fine", "portal", "full")

    runs.complete_run("run_fine", 3, 1, 1, 1)

    row = runs.get_latest_run("portal")
    assert row["status"] == "completed"
    assert row["completed_at"] is not None


def test_list_by_source_run_returns_records_created_for_that_run(db):
    raw = RawRecordRepository(db)
    raw.upsert_raw_record(
        raw_record_id="raw_1",
        source_run_id="run_1",
        source_id="portal",
        external_id="ext-1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        source_url=None,
        raw_text="<html></html>",
        raw_json=None,
        content_hash="sha256:aaa",
    )

    rows = raw.list_by_source_run("run_1")
    other = raw.list_by_source_run("run_other")

    assert [row["raw_record_id"] for row in rows] == ["raw_1"]
    assert other == []


def test_get_for_candidate_with_field_filter_returns_only_matching_fields(db):
    evidence = EvidenceRepository(db)
    evidence.insert_evidence(
        evidence_id="ev_1",
        candidate_id="cand_1",
        source_provider="wikidata",
        source_url=None,
        retrieved_at="2026-01-01T00:00:00+00:00",
        field="sector",
        value="logistics",
        confidence="high",
        trust_level="official",
        snippet=None,
        content_hash="sha256:aaa",
    )
    evidence.insert_evidence(
        evidence_id="ev_2",
        candidate_id="cand_1",
        source_provider="github",
        source_url=None,
        retrieved_at="2026-01-01T00:00:00+00:00",
        field="github_org",
        value="acme",
        confidence="medium",
        trust_level="public",
        snippet=None,
        content_hash="sha256:bbb",
    )

    rows = evidence.get_for_candidate("cand_1", fields=["sector"])
    counts = evidence.count_for_candidate("cand_1")

    assert [row["field"] for row in rows] == ["sector"]
    assert counts == 2


def test_count_for_candidate_returns_zero_without_evidence(db):
    assert EvidenceRepository(db).count_for_candidate("cand_missing") == 0


def test_insert_evidence_returns_the_existing_id_for_duplicate_content(db):
    evidence = EvidenceRepository(db)
    kwargs = {
        "candidate_id": "cand_1",
        "source_provider": "wikidata",
        "source_url": None,
        "retrieved_at": "2026-01-01T00:00:00+00:00",
        "field": "sector",
        "value": "logistics",
        "confidence": "high",
        "trust_level": "official",
        "snippet": None,
        "content_hash": "sha256:aaa",
    }

    first = evidence.insert_evidence(evidence_id="ev_1", **kwargs)
    duplicate = evidence.insert_evidence(evidence_id="ev_2", **kwargs)

    assert first == "ev_1"
    assert duplicate == "ev_1"


def test_get_detail_returns_none_for_an_unknown_candidate(db):
    assert CandidateRepository(db).get_detail("cand_missing") is None


def test_insert_claim_returns_the_existing_claim_id_on_duplicate_content(db):
    CandidateRepository(db).upsert_candidate(
        "cand_1", "Firm A", "GmbH", None, None, None, None, None, "raw_candidate"
    )
    claims = EnrichmentClaimRepository(db)
    first = claims.insert_claim(
        claim_id="claim_1",
        candidate_id="cand_1",
        source_provider="wikidata",
        source_url="https://www.wikidata.org/wiki/Q1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        field="sector",
        value="logistics",
        classification="verified",
        note=None,
        content_hash="sha256:aaa",
    )
    duplicate = claims.insert_claim(
        claim_id="claim_2",
        candidate_id="cand_1",
        source_provider="wikidata",
        source_url="https://www.wikidata.org/wiki/Q1",
        retrieved_at="2026-01-02T00:00:00+00:00",
        field="sector",
        value="logistics",
        classification="verified",
        note=None,
        content_hash="sha256:aaa",
    )

    rows = claims.get_for_candidate("cand_1")

    assert first == "claim_1"
    assert duplicate == "claim_1"
    assert [row["claim_id"] for row in rows] == ["claim_1"]
    assert claims.count_for_candidate("cand_1") == 1


def test_save_enrichment_then_get_enrichment_returns_the_stored_summary(db):
    CandidateRepository(db).upsert_candidate(
        "cand_1", "Firm A", "GmbH", None, None, None, None, None, "raw_candidate"
    )
    enrichment = EnrichmentRepository(db)

    enrichment_id = enrichment.save_enrichment(
        "cand_1",
        sector="logistics",
        employee_count_range="201-500",
        website_url="https://acme.example",
        website_status="200",
    )
    stored = enrichment.get_enrichment("cand_1")

    assert stored is not None
    assert stored["id"] == enrichment_id
    assert stored["sector"] == "logistics"
    assert stored["website_status"] == "200"
