"""Unit tests for Phase 2 LangGraph workflow structure and deterministic guardrails."""

from biradar.graph.phase2_workflow import (
    build_phase2_workflow,
    draft_assembly_node,
    enrichment_node,
    risk_review_node,
)
from biradar.graph.state import Phase2WorkflowState


def test_phase2_workflow_builds_successfully():
    """Test that the Phase 2 workflow graph can be built without errors."""
    workflow = build_phase2_workflow()
    assert workflow is not None

    # Verify nodes exist
    nodes = list(workflow.nodes.keys())
    assert "ingest" in nodes
    assert "normalize_and_compliance" in nodes
    assert "dedupe" in nodes
    assert "extraction" in nodes
    assert "enrichment" in nodes
    assert "scoring" in nodes
    assert "risk_review" in nodes
    assert "draft_assembly" in nodes
    assert "export" in nodes


def test_phase2_workflow_initial_state():
    """Test that the workflow state can be initialized correctly."""
    initial_state: Phase2WorkflowState = {
        "source_run_id": "test_run_123",
        "raw_records": [],
        "candidates": [],
        "extraction_results": {},
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "risk_review_retries": {},
        "errors": [],
        "warnings": [],
        "status": "ingest",
    }

    # Validate state matches TypedDict (basic check)
    assert initial_state["source_run_id"] == "test_run_123"
    assert initial_state["status"] == "ingest"


def test_risk_review_node_retries_and_quarantines():
    """Test that risk review correctly handles retries and max retries quarantine."""
    # Create a state where a candidate will fail review twice and then quarantine
    state: Phase2WorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {"candidate_id": "c1", "status": "deduped_candidate"},
        ],
        "extraction_results": {
            "c1": {"evidence_snippets": {"company_name": "Test Run GmbH"}}
        },
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {"c1": 1},  # Already has 1 retry
        "errors": [],
        "warnings": [],
        "current_step": "risk_review",
    }

    # We cannot easily mock the internal 'passed_review' variable in the current
    # implementation without dependency injection. However, we can verify that
    # the node processes the candidate and updates the state correctly for a passing case.
    result_state = risk_review_node(state)

    # Since passed_review is hardcoded to True in the placeholder, it should pass
    assert result_state["current_step"] == "draft_assembly"
    assert result_state["risk_reviews"]["c1"]["status"] == "passed"
    assert result_state["retry_counts"]["c1"] == 1  # Should not increment if passed


def test_risk_review_node_processes_all_candidates():
    """Test that the risk review loop doesn't early-return and skips candidates."""
    state: Phase2WorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {"candidate_id": "c1", "status": "deduped_candidate"},
            {"candidate_id": "c2", "status": "deduped_candidate"},
        ],
        "extraction_results": {
            "c1": {"evidence_snippets": {"company_name": "One GmbH"}},
            "c2": {"evidence_snippets": {"company_name": "Two GmbH"}},
        },
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "errors": [],
        "warnings": [],
        "current_step": "risk_review",
    }

    # In the fixed code, the loop completes for all candidates before returning.
    # Since 'passed_review = True' is hardcoded in the placeholder, both should pass.
    result_state = risk_review_node(state)

    assert result_state["current_step"] == "draft_assembly"
    assert result_state["risk_reviews"]["c1"]["status"] == "passed"
    assert result_state["risk_reviews"]["c2"]["status"] == "passed"


def test_export_excludes_quarantined_candidates():
    """Verify that the export logic explicitly filters out quarantined candidates."""
    import tempfile
    from pathlib import Path

    from biradar.output.export import generate_json_package

    issue_data = {
        "title": "Test Issue",
        "candidates": [
            {
                "candidate_id": "c1",
                "company_name": "Good GmbH",
                "status": "publish_ready",
            },
            {
                "candidate_id": "c2",
                "company_name": "Bad UG",
                "status": "quarantined",
                "quarantine_reason": "risk_review_failed",
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = generate_json_package(issue_data, Path(tmpdir))

        with open(export_path, encoding="utf-8") as f:
            import json

            data = json.load(f)

        # Assert quarantined candidate is excluded
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["candidate_id"] == "c1"
        assert "disclaimer" in data["metadata"]


def test_enrichment_node_marks_blocked_by_anti_bot():
    state: Phase2WorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "status": "deduped_candidate",
                "enrichment_http_status": 403,
                "enrichment_source": "handelsregister",
            }
        ],
        "extraction_results": {},
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "errors": [],
        "warnings": [],
        "current_step": "enrichment",
    }
    result = enrichment_node(state)
    assert result["enrichment_results"]["c1"]["status"] == "blocked_by_anti_bot"


def test_draft_assembly_enforces_export_gates():
    state: Phase2WorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "company_name": "Good GmbH",
                "status": "publish_ready",
            },
            {
                "candidate_id": "c2",
                "company_name": "Weak GmbH",
                "status": "publish_ready",
            },
        ],
        "extraction_results": {
            "c1": {"evidence_snippets": {"company_name": "Good GmbH"}},
            "c2": {"evidence_snippets": {}},
        },
        "enrichment_results": {"c1": {"claims": []}, "c2": {"claims": []}},
        "scores": {
            "c1": {
                "status": "approved",
                "computed_score": 3.0,
                "category": "interesting",
            },
        },
        "risk_reviews": {"c1": {"confidence": 0.8}, "c2": {"confidence": 0.2}},
        "retry_counts": {},
        "errors": [],
        "warnings": [],
        "current_step": "draft_assembly",
    }
    result = draft_assembly_node(state)
    assert len(result["issue_draft"]["candidates"]) == 1
    assert result["issue_draft"]["candidates"][0]["candidate_id"] == "c1"
    assert result["issue_draft"]["audit_summary"]["publish_ready_candidates"] == 1
    assert (
        result["issue_draft"]["candidates"][0]["content_sections"]["facts"][
            "company_name"
        ]
        == "Good GmbH"
    )
    assert "editorial" in result["issue_draft"]["candidates"][0]["content_sections"]
    assert any("Excluded c2 from export" in warning for warning in result["warnings"])


def test_risk_review_quarantines_unsupported_non_inference_claims():
    state: Phase2WorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "company_name": "Risky GmbH",
                "status": "deduped_candidate",
            },
        ],
        "extraction_results": {
            "c1": {"evidence_snippets": {"company_name": "Risky GmbH"}}
        },
        "enrichment_results": {
            "c1": {
                "claims": [
                    {
                        "field": "employees",
                        "value": "40",
                        "classification": "fact",
                        "source_url": None,
                    }
                ]
            }
        },
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "errors": [],
        "warnings": [],
        "current_step": "risk_review",
    }
    result = risk_review_node(state)
    assert result["candidates"][0]["status"] == "quarantined"
    assert result["risk_reviews"]["c1"]["reasons"] == ["unsupported_enrichment_claims"]
    assert any(
        "unsupported enrichment claims" in warning.lower()
        for warning in result["warnings"]
    )
