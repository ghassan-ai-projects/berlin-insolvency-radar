"""The radar tool registry: the spec order is contractual."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from biradar.mcp.schemas import (
    AuditTrailInput,
    CreateIssueDraftInput,
    ExportIssueInput,
    GetCandidateInput,
    HealthInput,
    ImportLegacyScoutInput,
    ListCandidatesInput,
    ListSourceRunsInput,
    ReviewCandidateInput,
    RunWorkflowInput,
)
from biradar.mcp.server.handlers import (
    _audit_trail,
    _check_health,
    _create_issue_draft,
    _export_issue,
    _get_candidate,
    _import_legacy_scout,
    _list_candidates,
    _list_source_runs,
    _review_candidate,
    _run_workflow,
)


@dataclass(frozen=True)
class RadarToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Any


def _tool_specs() -> list[RadarToolSpec]:
    """Return the ordered radar tool registry (fresh list per call)."""
    return [
        RadarToolSpec(
            name="radar_health",
            description="Check application health, database status, and next recommended action.",
            input_model=HealthInput,
            handler=_check_health,
        ),
        RadarToolSpec(
            name="radar_import_legacy_scout",
            description="Import or dry-run import from legacy insolvency_scout DuckDB.",
            input_model=ImportLegacyScoutInput,
            handler=_import_legacy_scout,
        ),
        RadarToolSpec(
            name="radar_list_candidates",
            description="List candidates, defaulting to those needing work.",
            input_model=ListCandidatesInput,
            handler=_list_candidates,
        ),
        RadarToolSpec(
            name="radar_get_candidate",
            description="Get full candidate detail with evidence and lineage.",
            input_model=GetCandidateInput,
            handler=_get_candidate,
        ),
        RadarToolSpec(
            name="radar_review_candidate",
            description="Review a candidate: approve, reject, needs_more_info, mark_duplicate, or archive.",
            input_model=ReviewCandidateInput,
            handler=_review_candidate,
        ),
        RadarToolSpec(
            name="radar_create_issue_draft",
            description="Create a newsletter issue draft from approved candidates.",
            input_model=CreateIssueDraftInput,
            handler=_create_issue_draft,
        ),
        RadarToolSpec(
            name="radar_export_issue",
            description="Export an issue draft to a local Markdown file.",
            input_model=ExportIssueInput,
            handler=_export_issue,
        ),
        RadarToolSpec(
            name="radar_audit_trail",
            description="Retrieve audit events for an entity.",
            input_model=AuditTrailInput,
            handler=_audit_trail,
        ),
        RadarToolSpec(
            name="radar_list_source_runs",
            description="Inspect source-run history for official acquisition runs.",
            input_model=ListSourceRunsInput,
            handler=_list_source_runs,
        ),
        RadarToolSpec(
            name="radar_run_workflow",
            description="Trigger the production workflow pipeline from ingestion to local export.",
            input_model=RunWorkflowInput,
            handler=_run_workflow,
        ),
    ]
