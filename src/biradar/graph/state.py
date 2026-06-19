"""LangGraph state models for workflows."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ImportWorkflowState(TypedDict):
    source_id: str
    dry_run: bool
    raw_records_seen: int
    candidates_imported: int
    duplicates: int
    rejected: int
    status: str
    error: NotRequired[str]


class ReviewWorkflowState(TypedDict):
    candidate_id: str
    decision: str
    reviewer: str
    score_input: NotRequired[dict]
    note: NotRequired[str]
    new_status: NotRequired[str]
    computed_score: NotRequired[float]
    status: str
    error: NotRequired[str]


class HealthWorkflowState(TypedDict):
    actor: str
    status: str
    database_connected: NotRequired[bool]
    database_path: NotRequired[str]
    schema_version: NotRequired[str]
    candidate_count: NotRequired[int]
    source_run_count: NotRequired[int]
    audit_id: NotRequired[str]
    error: NotRequired[str]


class EnrichmentClaimPayload(TypedDict):
    field: str
    value: str
    classification: str
    source_provider: str
    source_url: str | None
    note: str | None


class ExtractionPayload(TypedDict, total=False):
    company_name: str
    legal_form: str
    court: str
    case_number: str
    filing_date: str
    proceeding_stage: str
    is_consumer_likely: bool
    field_confidence_scores: dict[str, float]
    evidence_snippets: dict[str, str]


class EnrichmentStageResult(TypedDict):
    enriched: bool
    status: str
    claims: list[EnrichmentClaimPayload]
    note: NotRequired[str]
    data: dict[str, Any]
    errors: list[str]


class ScorePayload(TypedDict, total=False):
    company_value: int
    asset_quality: int
    sector_attractiveness: int
    speed_of_action: int
    legal_risk: int
    computed_score: float
    category: str
    status: str
    rationale: dict[str, str]
    error: str


class RiskReviewPayload(TypedDict, total=False):
    status: str
    retries: int
    confidence: float
    reasons: list[str]
    unsupported_claims: list[dict[str, Any]]


class CandidateRecord(TypedDict, total=False):
    raw_record_id: str
    source_url: str
    candidate_id: str
    company_name: str
    legal_form: str | None
    court: str | None
    case_number: str | None
    register_number: str | None
    publication_date: str | None
    publication_type: str | None
    proceeding_stage: str | None
    raw_text: str
    source_run_id: str
    source_quality: str
    status: str
    compliance_reason: str | None
    quarantine_reason: str | None
    risk_flags: list[str] | None
    score: ScorePayload
    export_confidence: float | None
    evidence_summary: dict[str, str]
    enrichment_claims: list[EnrichmentClaimPayload]
    unsupported_claims: list[dict[str, Any]]
    content_sections: dict[str, Any]


class PipelineWorkflowState(TypedDict):
    """State for the fully agentic pipeline.

    Per architecture rules, this state carries transient execution data
    (like candidate dicts for the duration of a single run) and workflow metadata.
    Durable, long-term facts are persisted to DuckDB via repository layers.
    """

    source_run_id: str
    raw_records: list[CandidateRecord]  # Transient for current run execution
    already_processed_raw_ids: NotRequired[list[str]]  # Raw IDs with linked candidates
    candidates: list[CandidateRecord]  # Transient for current run execution
    extraction_results: dict[str, ExtractionPayload]
    enrichment_results: dict[str, EnrichmentStageResult]
    scores: dict[str, ScorePayload]
    risk_reviews: dict[str, RiskReviewPayload]
    retry_counts: dict[str, int]
    issue_draft: NotRequired[dict]
    issue_id: NotRequired[str]
    export_path: NotRequired[str]
    current_step: Literal[
        "ingest",
        "normalize",
        "dedupe",
        "extraction",
        "enrichment",
        "scoring",
        "risk_review",
        "draft_assembly",
        "export",
        "completed",
        "failed",
    ]
    errors: list[str]
    warnings: list[str]


def build_initial_pipeline_state(
    *,
    source_run_id: str,
    raw_records: list[CandidateRecord],
    already_processed_raw_ids: list[str] | None = None,
) -> PipelineWorkflowState:
    """Build the canonical initial pipeline state."""
    return {
        "source_run_id": source_run_id,
        "raw_records": raw_records,
        "already_processed_raw_ids": already_processed_raw_ids or [],
        "candidates": [],
        "extraction_results": {},
        "enrichment_results": {},
        "scores": {},
        "risk_reviews": {},
        "retry_counts": {},
        "current_step": "ingest",
        "errors": [],
        "warnings": [],
    }
