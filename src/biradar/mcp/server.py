"""MCP Server for Berlin Insolvency Radar."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, ValidationError

from biradar.mcp.envelope import ResultEnvelope
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
from biradar.services.container import AppContainer
from biradar.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RadarToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Any


def _workflow_result_to_envelope(result: dict[str, Any]) -> ResultEnvelope[Any]:
    return ResultEnvelope(
        ok=result.get("status") == "success",
        data=result,
        errors=(
            []
            if result.get("status") == "success"
            else [
                {
                    "code": "WORKFLOW_FAILED",
                    "message": result.get("error", "Workflow failed."),
                    "retryable": True,
                }
            ]
        ),
        next_action=(
            "Inspect radar_audit_trail and exported artifacts."
            if result.get("status") == "success"
            else "Review the workflow error and retry the run."
        ),
    )


def _tool_specs() -> list[RadarToolSpec]:
    return [
        RadarToolSpec(
            name="radar_health",
            description="Check application health, database status, and next recommended action.",
            input_model=HealthInput,
            handler=lambda container, _params: container.health.check(),
        ),
        RadarToolSpec(
            name="radar_import_legacy_scout",
            description="Import or dry-run import from legacy insolvency_scout DuckDB.",
            input_model=ImportLegacyScoutInput,
            handler=lambda container, params: (
                container.legacy_import.import_legacy_scout(params)
            ),
        ),
        RadarToolSpec(
            name="radar_list_candidates",
            description="List candidates, defaulting to those needing work.",
            input_model=ListCandidatesInput,
            handler=lambda container, params: container.candidates.list_candidates(
                statuses=list(params.statuses) if params.statuses else None,
                limit=params.limit,
                offset=params.offset,
            ),
        ),
        RadarToolSpec(
            name="radar_get_candidate",
            description="Get full candidate detail with evidence and lineage.",
            input_model=GetCandidateInput,
            handler=lambda container, params: container.candidates.get_candidate(
                params.candidate_id
            ),
        ),
        RadarToolSpec(
            name="radar_review_candidate",
            description="Review a candidate: approve, reject, needs_more_info, mark_duplicate, or archive.",
            input_model=ReviewCandidateInput,
            handler=lambda container, params: container.reviews.review_candidate(
                candidate_id=params.candidate_id,
                decision=params.decision,
                reviewer=params.reviewer,
                note=params.note,
                score_input=(
                    params.score_input.model_dump() if params.score_input else None
                ),
            ),
        ),
        RadarToolSpec(
            name="radar_create_issue_draft",
            description="Create a newsletter issue draft from approved candidates.",
            input_model=CreateIssueDraftInput,
            handler=lambda container, params: container.issues.create_issue_draft(
                week=params.week,
                tier=params.tier,
                candidate_ids=params.candidate_ids,
                title=params.title,
                include_disclaimer=params.include_disclaimer,
                actor=params.actor,
            ),
        ),
        RadarToolSpec(
            name="radar_export_issue",
            description="Export an issue draft to a local Markdown file.",
            input_model=ExportIssueInput,
            handler=lambda container, params: container.issues.export_issue(
                issue_id=params.issue_id,
                format=params.format,
                actor=params.actor,
            ),
        ),
        RadarToolSpec(
            name="radar_audit_trail",
            description="Retrieve audit events for an entity.",
            input_model=AuditTrailInput,
            handler=lambda container, params: ResultEnvelope(
                ok=True,
                data=container.audit_repo.get_events(
                    entity_type=params.entity_type,
                    entity_id=params.entity_id,
                    actor=params.actor,
                    limit=params.limit,
                ),
            ),
        ),
        RadarToolSpec(
            name="radar_list_source_runs",
            description="Inspect source-run history for official acquisition runs.",
            input_model=ListSourceRunsInput,
            handler=lambda container, params: ResultEnvelope(
                ok=True,
                data=container.health.source_repo.list_runs(
                    source_id=params.source_id,
                    status=params.status,
                    limit=params.limit,
                ),
            ),
        ),
        RadarToolSpec(
            name="radar_run_workflow",
            description="Trigger the production workflow pipeline from ingestion to local export.",
            input_model=RunWorkflowInput,
            handler=lambda _container, params: _workflow_result_to_envelope(
                run_pipeline(
                    start_date=params.start_date,
                    end_date=params.end_date,
                    dry_run=params.dry_run,
                )
            ),
        ),
    ]


def list_radar_tools() -> list[Tool]:
    """Return the MCP tool definitions derived from schema models."""
    return [
        Tool(
            name=spec.name,
            description=spec.description,
            inputSchema=spec.input_model.model_json_schema(),
        )
        for spec in _tool_specs()
    ]


def validation_error(message: str) -> ResultEnvelope[Any]:
    """Build a stable validation failure envelope."""
    return ResultEnvelope(
        ok=False,
        errors=[
            {
                "code": "VALIDATION_ERROR",
                "message": message,
                "retryable": False,
                "next_action": "Fix the tool arguments and retry.",
            }
        ],
        next_action="Fix the tool arguments and retry.",
    )


def call_radar_tool(
    container: AppContainer, name: str, arguments: dict[str, Any] | None = None
) -> ResultEnvelope[Any]:
    """Execute a radar tool through the same path used by MCP."""
    args = arguments or {}
    spec_by_name = {spec.name: spec for spec in _tool_specs()}

    try:
        spec = spec_by_name.get(name)
        if spec is None:
            return ResultEnvelope(
                ok=False,
                errors=[
                    {
                        "code": "TOOL_NOT_FOUND",
                        "message": f"Unknown tool: {name}",
                        "retryable": False,
                    }
                ],
            )

        params = spec.input_model(**args)
        return spec.handler(container, params)
    except ValidationError as e:
        return validation_error(str(e))
    except Exception:
        logger.exception("Unhandled error in radar tool dispatch", extra={"tool": name})
        return ResultEnvelope(
            ok=False,
            errors=[
                {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred.",
                    "retryable": True,
                }
            ],
        )


def create_mcp_server(config_dir: Path, db_path: Path) -> Server:
    """Create and configure the MCP server."""
    server = Server("biradar")
    container = AppContainer(config_dir, db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return list_radar_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = call_radar_tool(container, name, arguments)
        return [
            TextContent(
                type="text",
                text=json.dumps(result.model_dump(), indent=2, default=str),
            )
        ]

    return server
