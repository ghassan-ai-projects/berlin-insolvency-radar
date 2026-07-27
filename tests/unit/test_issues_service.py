"""Unit tests for the newsletter issue service."""

import json
from datetime import UTC, datetime

import pytest

from biradar.services.issues import IssueService
from biradar.storage.db import Database


def _raises(exc):
    """Return a stand-in that raises when the service calls it."""

    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


@pytest.fixture
def service(tmp_path):
    db = Database(tmp_path / "radar.duckdb")
    db.run_migrations()
    yield IssueService(db, tmp_path / "exports")
    db.close()


def _publishable_candidate(service, cid="c1", *, evidence_field="company_name"):
    service.candidate_repo.upsert_candidate(
        candidate_id=cid,
        company_name="Acme GmbH",
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status="publish_ready",
    )
    service.score_repo.insert_score(
        score_id=f"score_{cid}",
        candidate_id=cid,
        score_version="v1",
        company_value=3,
        asset_quality=3,
        sector_attractiveness=3,
        speed_of_action=3,
        legal_risk=2,
        computed_score=3.5,
        category="solid",
        rationale_json=json.dumps({"method": "test"}),
        status="approved",
        reviewer="analyst@example.com",
    )
    service.evidence_repo.insert_evidence(
        evidence_id=f"ev_{cid}_{evidence_field}",
        candidate_id=cid,
        source_provider="official_portal",
        source_url="https://example.invalid/x",
        retrieved_at=datetime.now(UTC).isoformat(),
        field=evidence_field,
        value="Acme GmbH",
        confidence="high",
        trust_level="A",
        snippet="Acme GmbH",
        content_hash=f"sha256:{cid}{evidence_field}",
    )
    return cid


def _draft(service, **overrides):
    kwargs = {
        "week": "2026-W25",
        "tier": "paid",
        "candidate_ids": ["c1"],
        "title": "Weekly Radar",
    }
    return service.create_issue_draft(**{**kwargs, **overrides})


def test_create_draft_rejects_unknown_tier(service):
    result = _draft(service, tier="enterprise")

    assert not result.ok
    assert result.errors[0]["code"] == "INVALID_TIER"
    assert result.audit_id is not None


def test_create_draft_succeeds_for_publishable_candidate(service):
    _publishable_candidate(service)

    result = _draft(service)

    assert result.ok
    assert result.data["candidate_count"] == 1
    assert result.data["status"] == "draft"


def test_create_draft_warns_about_missing_candidate(service):
    result = _draft(service, candidate_ids=["nope"])

    assert any("not found" in w for w in result.warnings)


def test_create_draft_skips_candidate_that_is_not_publish_ready(service):
    service.candidate_repo.upsert_candidate(
        candidate_id="c1",
        company_name="Acme GmbH",
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status="needs_review",
    )

    result = _draft(service)

    assert any("not publish_ready" in w for w in result.warnings)


def test_create_draft_skips_candidate_without_approved_score(service):
    service.candidate_repo.upsert_candidate(
        candidate_id="c1",
        company_name="Acme GmbH",
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status="publish_ready",
    )

    result = _draft(service)

    assert any("no approved score" in w for w in result.warnings)


def test_create_draft_skips_candidate_without_evidence(service):
    _publishable_candidate(service)
    service.db.conn.execute("DELETE FROM evidence_items")

    result = _draft(service)

    assert any("no evidence" in w for w in result.warnings)


def test_free_tier_suppresses_administrator_evidence(service):
    """Free tier must not leak insolvency administrator contact details."""
    _publishable_candidate(service, evidence_field="administrator_contact")

    result = _draft(service, tier="free")

    assert not result.ok
    assert result.errors[0]["code"] == "NO_VALID_CANDIDATES"
    assert any("no publishable evidence" in w for w in result.warnings)


def test_paid_tier_retains_administrator_evidence(service):
    _publishable_candidate(service, evidence_field="administrator_contact")

    result = _draft(service, tier="paid")

    assert result.data["candidate_count"] == 1


def test_create_draft_returns_generic_error_envelope_on_failure(service):
    service.candidate_repo.get_by_id = _raises(RuntimeError("boom"))

    result = _draft(service)

    assert not result.ok
    assert result.errors[0]["code"] == "CREATE_DRAFT_FAILED"
    assert "boom" not in json.dumps(result.model_dump(), default=str)


def test_export_rejects_unsupported_format(service):
    _publishable_candidate(service)
    issue_id = _draft(service).data["issue_id"]

    result = service.export_issue(issue_id=issue_id, format="pdf")

    assert not result.ok
    assert result.errors[0]["code"] == "UNSUPPORTED_FORMAT"


def test_export_reports_missing_issue(service):
    result = service.export_issue(issue_id="missing")

    assert not result.ok
    assert result.errors[0]["code"] == "ISSUE_NOT_FOUND"


def test_export_writes_markdown_file_and_hash(service):
    _publishable_candidate(service)
    issue_id = _draft(service).data["issue_id"]

    result = service.export_issue(issue_id=issue_id)

    assert result.ok
    assert result.data["path"].endswith("issue-2026-W25-paid.md")
    assert result.data["sha256"]


def test_export_is_rejected_for_an_already_exported_issue(service):
    _publishable_candidate(service)
    issue_id = _draft(service).data["issue_id"]
    service.export_issue(issue_id=issue_id)

    second = service.export_issue(issue_id=issue_id)

    assert not second.ok


def test_export_returns_generic_error_envelope_on_failure(service):
    _publishable_candidate(service)
    issue_id = _draft(service).data["issue_id"]
    service.issue_repo.mark_exported = _raises(RuntimeError("disk on fire"))

    result = service.export_issue(issue_id=issue_id)

    assert not result.ok
    assert result.errors[0]["code"] == "EXPORT_FAILED"
    assert "disk on fire" not in json.dumps(result.model_dump(), default=str)
