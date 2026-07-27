"""Unit tests for the candidate query service."""

import json
from datetime import UTC, datetime

import pytest

from biradar.services.candidates import CandidateService
from biradar.storage.db import Database


def _raises(exc):
    """Return a stand-in that raises when the service calls it."""

    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "radar.duckdb")
    database.run_migrations()
    yield database
    database.close()


@pytest.fixture
def service(db):
    return CandidateService(db)


def _add_candidate(service, candidate_id, status="needs_review", name="Acme GmbH"):
    service.candidate_repo.upsert_candidate(
        candidate_id=candidate_id,
        company_name=name,
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status=status,
    )


def _add_score(service, candidate_id, status="proposed", computed=3.5):
    service.score_repo.insert_score(
        score_id=f"score_{candidate_id}",
        candidate_id=candidate_id,
        score_version="v1",
        company_value=3,
        asset_quality=3,
        sector_attractiveness=3,
        speed_of_action=3,
        legal_risk=2,
        computed_score=computed,
        category="solid",
        rationale_json=json.dumps({"method": "test"}),
        status=status,
        reviewer="analyst@example.com",
    )


def test_list_candidates_returns_empty_list_when_none_match(service):
    result = service.list_candidates()
    assert result.ok
    assert result.data == []


def test_list_candidates_defaults_to_statuses_needing_work(service):
    _add_candidate(service, "c_needs", status="needs_review")
    _add_candidate(service, "c_archived", status="archived")

    result = service.list_candidates()

    ids = {c["candidate_id"] for c in result.data}
    assert ids == {"c_needs"}


def test_list_candidates_honours_explicit_status_filter(service):
    _add_candidate(service, "c_archived", status="archived")

    result = service.list_candidates(statuses=["archived"])

    assert [c["candidate_id"] for c in result.data] == ["c_archived"]


def test_list_candidates_marks_unscored_candidates(service):
    _add_candidate(service, "c1")

    result = service.list_candidates()

    assert result.data[0]["score_status"] == "unscored"
    assert result.data[0]["latest_score"] is None


def test_list_candidates_reports_latest_score(service):
    _add_candidate(service, "c1")
    _add_score(service, "c1", status="proposed", computed=4.25)

    result = service.list_candidates()

    assert result.data[0]["score_status"] == "proposed"
    assert result.data[0]["latest_score"] == pytest.approx(4.25)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("needs_review", "Review and score this candidate."),
        ("review_ready", "Approve score to mark publish_ready."),
        ("publish_ready", "Candidate is ready for issue inclusion."),
    ],
)
def test_list_candidates_sets_status_specific_next_action(service, status, expected):
    _add_candidate(service, "c1", status=status)

    result = service.list_candidates()

    assert result.data[0]["next_action"] == expected


def test_list_candidates_includes_evidence_count(service):
    _add_candidate(service, "c1")
    service.evidence_repo.insert_evidence(
        evidence_id="ev_1",
        candidate_id="c1",
        source_provider="official_portal",
        source_url="https://example.invalid/x",
        retrieved_at=datetime.now(UTC).isoformat(),
        field="company_name",
        value="Acme GmbH",
        confidence="high",
        trust_level="A",
        snippet="Acme GmbH",
        content_hash="sha256:abc",
    )

    result = service.list_candidates()

    assert result.data[0]["evidence_count"] == 1


def test_list_candidates_applies_limit_and_offset(service):
    for i in range(3):
        _add_candidate(service, f"c{i}", name=f"Company {i} GmbH")

    page = service.list_candidates(limit=2, offset=0)
    rest = service.list_candidates(limit=2, offset=2)

    assert len(page.data) == 2
    assert len(rest.data) == 1


def test_list_candidates_returns_generic_error_envelope_on_failure(service):
    service.candidate_repo.get_by_status = _raises(RuntimeError("boom"))

    result = service.list_candidates()

    assert not result.ok
    assert result.errors[0]["code"] == "LIST_CANDIDATES_FAILED"
    assert "boom" not in json_dump(result), "internal detail leaked to the caller"


def json_dump(envelope) -> str:
    return json.dumps(envelope.model_dump(), default=str)


def test_get_candidate_returns_not_found_for_unknown_id(service):
    result = service.get_candidate("missing")

    assert not result.ok
    assert result.errors[0]["code"] == "CANDIDATE_NOT_FOUND"
    assert result.errors[0]["retryable"] is False


def test_get_candidate_returns_detail_for_known_id(service):
    _add_candidate(service, "c1")

    result = service.get_candidate("c1")

    assert result.ok
    assert result.data["candidate"]["candidate_id"] == "c1"


def test_get_candidate_detail_includes_all_lineage_sections(service):
    _add_candidate(service, "c1")

    data = service.get_candidate("c1").data

    assert set(data) == {
        "candidate",
        "evidence",
        "scores",
        "reviews",
        "source_lineage",
        "enrichment_summary",
        "enrichment_claims",
        "audit_events",
    }


def test_get_candidate_returns_generic_error_envelope_on_failure(service):
    _add_candidate(service, "c1")
    service.candidate_repo.get_detail = _raises(RuntimeError("boom"))

    result = service.get_candidate("c1")

    assert not result.ok
    assert result.errors[0]["code"] == "GET_CANDIDATE_FAILED"
    assert "boom" not in json_dump(result), "internal detail leaked to the caller"
