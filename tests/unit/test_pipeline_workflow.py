"""Unit tests for LangGraph workflow structure and deterministic guardrails."""

from biradar.agents.risk_review import RiskReviewResult
from biradar.graph.pipeline_workflow import (
    build_pipeline_workflow,
    draft_assembly_node,
    enrichment_node,
    risk_review_node,
)
from biradar.graph.state import PipelineWorkflowState
from biradar.sources.enrichment import EnrichmentResult


def _passing_review(*args, **kwargs) -> RiskReviewResult:
    return RiskReviewResult(
        passed_review=True,
        rejection_reasons=None,
        actionable_feedback_for_analyst=None,
        flagged_unsupported_claims=[],
        confidence_in_review=0.8,
    )


def test_pipeline_workflow_builds_successfully():
    workflow = build_pipeline_workflow()
    assert workflow is not None
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


def test_pipeline_workflow_initial_state():
    initial_state: PipelineWorkflowState = {
        "source_run_id": "test_run_123",
        "raw_records": [],
        "candidates": [],
        "extraction_results": {},
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "errors": [],
        "warnings": [],
        "current_step": "ingest",
    }
    assert initial_state["source_run_id"] == "test_run_123"
    assert initial_state["current_step"] == "ingest"


def test_risk_review_node_records_passed_review():
    state: PipelineWorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [{"candidate_id": "c1", "status": "deduped_candidate"}],
        "extraction_results": {
            "c1": {"evidence_snippets": {"company_name": "Test Run GmbH"}}
        },
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {"c1": 1},
        "errors": [],
        "warnings": [],
        "current_step": "risk_review",
    }
    result_state = risk_review_node(state, risk_reviewer=_passing_review)
    assert result_state["current_step"] == "draft_assembly"
    assert result_state["risk_reviews"]["c1"]["status"] == "passed"
    assert result_state["retry_counts"]["c1"] == 1


def test_risk_review_node_processes_all_candidates():
    state: PipelineWorkflowState = {
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
    result_state = risk_review_node(state, risk_reviewer=_passing_review)
    assert result_state["current_step"] == "draft_assembly"
    assert result_state["risk_reviews"]["c1"]["status"] == "passed"
    assert result_state["risk_reviews"]["c2"]["status"] == "passed"


def test_export_excludes_quarantined_candidates():
    import json
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
        with open(export_path, encoding="utf-8") as handle:
            data = json.load(handle)

    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["candidate_id"] == "c1"
    assert "disclaimer" in data["metadata"]


def test_enrichment_node_marks_blocked_by_anti_bot():
    state: PipelineWorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "status": "deduped_candidate",
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
    assert result["enrichment_results"]["c1"]["status"] == "skipped"


def test_enrichment_node_uses_explicit_stub():
    def stub_enricher(company_name: str) -> EnrichmentResult:
        return EnrichmentResult(
            company_name=company_name,
            enriched=True,
            sources=[
                {
                    "source": "stub",
                    "url": "https://example.com",
                    "github_org": "stub-org",
                }
            ],
            errors=[],
            github_org="stub-org",
        )

    state: PipelineWorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "company_name": "Stub GmbH",
                "status": "deduped_candidate",
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
    result = enrichment_node(state, enricher=stub_enricher)
    assert result["enrichment_results"]["c1"]["status"] == "success"


def test_draft_assembly_enforces_export_gates():
    state: PipelineWorkflowState = {
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
            }
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
    state: PipelineWorkflowState = {
        "source_run_id": "test_run",
        "raw_records": [],
        "candidates": [
            {
                "candidate_id": "c1",
                "company_name": "Risky GmbH",
                "status": "deduped_candidate",
            }
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
