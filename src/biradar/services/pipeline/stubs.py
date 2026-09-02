"""Deterministic fixture records and agent stubs for validation runs."""

from collections.abc import Mapping
from typing import Any

from biradar.agents.extraction import ExtractionResult
from biradar.agents.risk_review import RiskReviewResult
from biradar.sources.enrichment import EnrichmentResult
from biradar.sources.official_portal import OfficialPortalAdapter


def _load_fixture_records(settings: Any) -> tuple[str, list[dict[str, Any]]]:
    """Load fixture-backed source data for validation execution."""
    fixture_path = (
        settings.project_root
        / "tests"
        / "fixtures"
        / "official_portal"
        / "sample_response.html"
    )
    adapter = OfficialPortalAdapter(db=None)
    records = adapter._parse_response(fixture_path.read_text(encoding="utf-8"))
    return "fixture_validation_run", records


def _stub_extractor(raw_text: str, source_url: str) -> ExtractionResult:
    return ExtractionResult(
        company_name="Test Berlin GmbH",
        legal_form="GmbH",
        court="Amtsgericht Charlottenburg",
        case_number="36e IN 123/26",
        filing_date="2026-06-15",
        proceeding_stage="Eroeffnungsbeschluss",
        is_consumer_likely=False,
        field_confidence_scores={"company_name": 0.95, "case_number": 0.93},
        evidence_snippets={
            "company_name": "Test Berlin GmbH",
            "case_number": "36e IN 123/26",
        },
    )


def _stub_risk_reviewer(
    candidate_data: Mapping[str, Any],
    extraction_data: Mapping[str, Any],
    enrichment_data: Mapping[str, Any],
    draft_thesis: str,
) -> RiskReviewResult:
    return RiskReviewResult(
        passed_review=True,
        rejection_reasons=None,
        actionable_feedback_for_analyst=None,
        flagged_unsupported_claims=[],
        confidence_in_review=0.88,
    )


def _stub_enricher(company_name: str) -> EnrichmentResult:
    return EnrichmentResult(
        company_name=company_name,
        sources=[
            {
                "source": "validation_stub",
                "url": "https://example.com/company",
                "registry_number": "HRB 123456 B",
                "registry_court": "Amtsgericht Charlottenburg",
                "legal_form": "GmbH",
                "company_status": "active",
                "tech_stack": "Python, FastAPI",
                "github_org": "test-berlin",
                "funding_info": "Reports available",
            }
        ],
        errors=[],
        enriched=True,
        sector="Legal form: GmbH",
        tech_stack="Python, FastAPI",
        website_url="https://example.com/company",
        website_status=200,
        github_org="test-berlin",
        funding_info="Reports available",
        legal_form="GmbH",
        registry_court="Amtsgericht Charlottenburg",
        registry_number="HRB 123456 B",
        company_status="active",
    )
