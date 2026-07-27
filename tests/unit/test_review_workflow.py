"""Unit tests for the review workflow graph."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from biradar.graph.review_workflow import (
    build_review_workflow,
    validate_and_review_node,
)
from biradar.mcp.envelope import ResultEnvelope
from biradar.services.container import AppContainer


@pytest.fixture
def container(tmp_path):
    config_dir = Path(__file__).parent.parent.parent / "config"
    container = AppContainer(config_dir, tmp_path / "radar.duckdb")
    yield container
    container.close()


def _state(**overrides):
    base = {
        "candidate_id": "cand_1",
        "decision": "approve",
        "reviewer": "analyst@example.com",
        "status": "pending",
    }
    return {**base, **overrides}


def _stub_container(envelope=None, exc=None):
    def review_candidate(**kwargs):
        if exc is not None:
            raise exc
        return envelope

    return SimpleNamespace(reviews=SimpleNamespace(review_candidate=review_candidate))


def test_node_reports_success_with_new_status_and_score():
    envelope = ResultEnvelope(
        ok=True, data={"status": "review_ready", "computed_score": 3.4}
    )

    result = validate_and_review_node(_state(), _stub_container(envelope))

    assert result["status"] == "success"
    assert result["new_status"] == "review_ready"
    assert result["computed_score"] == 3.4


def test_node_defaults_missing_score_to_none():
    envelope = ResultEnvelope(ok=True, data={"status": "rejected"})

    result = validate_and_review_node(
        _state(decision="reject"), _stub_container(envelope)
    )

    assert result["status"] == "success"
    assert result["computed_score"] is None


def test_node_reports_unknown_status_when_envelope_has_no_data():
    envelope = ResultEnvelope(ok=True, data=None)

    result = validate_and_review_node(_state(), _stub_container(envelope))

    assert result["new_status"] == "unknown"


def test_node_surfaces_service_error_message():
    envelope = ResultEnvelope(
        ok=False, errors=[{"code": "NOT_FOUND", "message": "Candidate not found"}]
    )

    result = validate_and_review_node(_state(), _stub_container(envelope))

    assert result["status"] == "failed"
    assert result["error"] == "Candidate not found"


def test_node_falls_back_when_failure_envelope_has_no_errors():
    envelope = ResultEnvelope(ok=False, errors=[])

    result = validate_and_review_node(_state(), _stub_container(envelope))

    assert result["status"] == "failed"
    assert result["error"] == "Unknown error"


def test_node_converts_unexpected_exception_into_failed_state():
    result = validate_and_review_node(
        _state(), _stub_container(exc=RuntimeError("db exploded"))
    )

    assert result["status"] == "failed"
    assert "db exploded" in result["error"]


def test_node_preserves_incoming_state_fields():
    envelope = ResultEnvelope(ok=True, data={"status": "review_ready"})

    result = validate_and_review_node(
        _state(note="looks good"), _stub_container(envelope)
    )

    assert result["candidate_id"] == "cand_1"
    assert result["reviewer"] == "analyst@example.com"
    assert result["note"] == "looks good"


def test_build_review_workflow_compiles(container):
    assert build_review_workflow(container) is not None


def test_compiled_review_workflow_runs_to_a_terminal_state(container):
    """An unknown candidate must terminate, not loop on the retry edge."""
    workflow = build_review_workflow(container)

    final = workflow.invoke(_state(candidate_id="does_not_exist"))

    assert final["status"] in ("success", "failed")
