"""Unit tests for the health service."""

import json
from pathlib import Path

import pytest

from biradar.config.settings import load_config
from biradar.services.health import HealthService
from biradar.storage.db import LATEST_SCHEMA_VERSION, Database


def _raises(exc):
    """Return a stand-in that raises when the service calls it."""

    def _raise(*_args, **_kwargs):
        raise exc

    return _raise


@pytest.fixture
def service(tmp_path):
    db = Database(tmp_path / "radar.duckdb")
    db.run_migrations()
    config = load_config(Path(__file__).parent.parent.parent / "config")
    yield HealthService(db, config)
    db.close()


def _add_candidate(service, candidate_id, status):
    service.candidate_repo.upsert_candidate(
        candidate_id=candidate_id,
        company_name="Acme GmbH",
        legal_form="GmbH",
        court="AG Charlottenburg",
        case_number="36e IN 1/26",
        register_number="HRB 1 B",
        publication_date="2026-06-15",
        publication_type="Eroeffnung",
        status=status,
    )


def test_check_reports_ok_on_a_migrated_database(service):
    result = service.check()

    assert result.ok
    assert result.data["status"] == "ok"
    assert result.data["database"]["connected"] is True
    assert result.data["database"]["schema_version"] == LATEST_SCHEMA_VERSION


def test_check_suggests_seeding_when_there_is_no_data(service):
    result = service.check()

    assert "No data yet" in result.data["next_action"]
    assert result.data["counts"] == {}


def test_check_prioritises_candidates_awaiting_review(service):
    _add_candidate(service, "c1", "needs_review")
    _add_candidate(service, "c2", "review_ready")

    result = service.check()

    assert result.data["next_action"] == "Review 1 candidates awaiting review."


def test_check_falls_back_to_review_ready_when_none_need_review(service):
    _add_candidate(service, "c1", "review_ready")

    result = service.check()

    assert result.data["next_action"] == "Approve 1 candidates ready for scoring."


def test_check_next_action_is_mirrored_on_the_envelope(service):
    _add_candidate(service, "c1", "needs_review")

    result = service.check()

    assert result.next_action == result.data["next_action"]


def test_check_reports_counts_grouped_by_status(service):
    _add_candidate(service, "c1", "needs_review")
    _add_candidate(service, "c2", "needs_review")
    _add_candidate(service, "c3", "archived")

    counts = service.check().data["counts"]

    assert counts["needs_review"] == 2
    assert counts["archived"] == 1


def test_check_reports_no_successful_source_run_initially(service):
    assert service.check().data["last_successful_source_run"] is None


def test_check_returns_generic_error_envelope_on_failure(service):
    service.candidate_repo.get_counts_by_status = _raises(RuntimeError("db exploded"))

    result = service.check()

    assert not result.ok
    assert result.errors[0]["code"] == "HEALTH_CHECK_FAILED"
    assert result.errors[0]["retryable"] is True
    body = json.dumps(result.model_dump(), default=str)
    assert "db exploded" not in body, "internal detail leaked to the caller"
