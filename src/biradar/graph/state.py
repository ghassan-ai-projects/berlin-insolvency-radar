"""LangGraph state models for workflows."""

from typing import Literal, NotRequired, TypedDict


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


class Phase0HealthWorkflowState(TypedDict):
    actor: str
    status: str
    database_connected: NotRequired[bool]
    database_path: NotRequired[str]
    schema_version: NotRequired[str]
    candidate_count: NotRequired[int]
    source_run_count: NotRequired[int]
    audit_id: NotRequired[str]
    error: NotRequired[str]


class Phase2WorkflowState(TypedDict):
    """State for the fully agentic Phase 2 pipeline.

    Per architecture rules, this state carries transient execution data
    (like candidate dicts for the duration of a single run) and workflow metadata.
    Durable, long-term facts are persisted to DuckDB via repository layers.
    """

    source_run_id: str
    raw_records: list[dict]  # Transient for current run execution
    candidates: list[dict]  # Transient for current run execution
    extraction_results: dict[str, dict]
    enrichment_results: dict[str, dict]
    scores: dict[str, dict]
    risk_reviews: dict[str, dict]
    retry_counts: dict[str, int]
    issue_draft: NotRequired[dict]
    issue_id: NotRequired[str]
    export_path: NotRequired[str]
    current_step: Literal[
        "ingest",
        "normalize",
        "compliance",
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
