"""Unit tests for the review service."""

from pathlib import Path

import pytest

from biradar.services.container import AppContainer


@pytest.fixture
def container(tmp_path):
    config_dir = Path(__file__).parent.parent.parent / "config"
    container = AppContainer(config_dir, tmp_path / "radar.duckdb")
    yield container
    container.close()


def _review_ready_candidate(container, cid="c1"):
    container.reviews.candidate_repo.upsert_candidate(
        candidate_id=cid,
        company_name="Acme GmbH",
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status="review_ready",
    )


def _raises(exc):
    """Return a stand-in that raises when the service calls it."""

    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


def test_review_rejects_invalid_decision(container):
    _review_ready_candidate(container)

    result = container.reviews.review_candidate(
        candidate_id="c1", decision="promote", reviewer="analyst@example.com"
    )

    assert not result.ok
    assert result.errors[0]["code"] == "INVALID_DECISION"
    assert result.errors[0]["message"].startswith("Decision must be one of {")
    assert result.audit_id is not None
    assert container.reviews.candidate_repo.get_by_id("c1")["status"] == "review_ready"


def test_approve_rejects_out_of_range_score_dimensions(container):
    _review_ready_candidate(container)

    result = container.reviews.review_candidate(
        candidate_id="c1",
        decision="approve",
        reviewer="analyst@example.com",
        score_input={
            "company_value": 9,
            "asset_quality": 3,
            "sector_attractiveness": 3,
            "speed_of_action": 3,
            "legal_risk": 2,
        },
    )

    assert not result.ok
    assert result.errors[0]["code"] == "INVALID_SCORE_INPUT"
    assert result.audit_id is not None
    assert container.reviews.candidate_repo.get_by_id("c1")["status"] == "review_ready"


def test_mark_duplicate_requires_note(container):
    _review_ready_candidate(container)

    result = container.reviews.review_candidate(
        candidate_id="c1", decision="mark_duplicate", reviewer="analyst@example.com"
    )

    assert not result.ok
    assert result.errors[0]["code"] == "NOTE_REQUIRED"
    assert "requires a note" in result.errors[0]["message"]


def test_review_returns_retryable_envelope_on_repo_failure(container):
    _review_ready_candidate(container)
    container.reviews.candidate_repo.get_by_id = _raises(RuntimeError("db gone"))

    result = container.reviews.review_candidate(
        candidate_id="c1", decision="reject", reviewer="analyst@example.com", note="dup"
    )

    assert not result.ok
    assert result.errors[0]["code"] == "REVIEW_FAILED"
    assert result.errors[0]["retryable"] is True
    assert result.audit_id is None
