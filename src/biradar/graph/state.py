"""LangGraph state models for workflows."""

from typing import NotRequired, TypedDict


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
